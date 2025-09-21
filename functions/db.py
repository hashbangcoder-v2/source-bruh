from __future__ import annotations

import base64
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2.credentials import Credentials


class FirestoreDB:
    """Small Firestore wrapper that also supports an in-memory fallback.

    The production deployment stores image metadata and embeddings inside
    Firestore.  For tests (or local development without credentials) we fall
    back to an in-memory store that mimics the Firestore API used by the
    server.  Image binaries can be provided either as raw bytes (``image_bytes``
    / ``thumb_bytes``) or as local file paths.  When only file paths are
    available the server reads from disk.
    """

    _IMAGES_COLLECTION = "images"

    def __init__(self, service_account_key_path: Optional[str]):
        self._service_account_key_path = service_account_key_path
        self._local_images: Dict[str, Dict[str, Any]] = {}
        self._local_users: Dict[str, Dict[str, Any]] = {}
        self._use_firestore = False

        key_path = Path(service_account_key_path) if service_account_key_path else None
        if key_path and key_path.exists():
            if not firebase_admin._apps:
                cred = credentials.Certificate(os.fspath(key_path))
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            self._use_firestore = True
        else:
            # Fall back to an in-memory store when credentials are missing.
            self.db = None

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------
    def add_image_data(self, image_data: Dict[str, Any], user_id: Optional[str] = None) -> str:
        """Persist metadata for an image and return its identifier."""

        data = dict(image_data)
        if user_id:
            data.setdefault("user_id", user_id)

        embedding = data.get("embedding")
        if embedding is not None:
            data["embedding"] = [float(x) for x in embedding]

        image_id = data.pop("image_id", None) or data.get("image_rowid")
        image_id = str(image_id) if image_id is not None else None

        if self._use_firestore:
            images_ref = self.db.collection(self._IMAGES_COLLECTION)
            if image_id:
                doc_ref = images_ref.document(image_id)
            else:
                doc_ref = images_ref.document()
                image_id = doc_ref.id
            data.setdefault("image_rowid", image_id)
            doc_ref.set(data)
        else:
            if image_id is None:
                image_id = str(len(self._local_images) + 1)
            data.setdefault("image_rowid", image_id)
            self._local_images[image_id] = data

        return image_id

    def search(self, query_vector: List[float], top_k: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return the ``top_k`` closest matches for ``query_vector``."""

        return self.search_vectors(query_vector=query_vector, top_k=top_k, user_id=user_id)

    def search_vectors(
        self, query_vector: List[float], top_k: int, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for doc_id, data in self._iter_image_documents(user_id=user_id):
            embedding = data.get("embedding")
            if not embedding:
                continue
            distance = self._cosine_distance(query_vector, embedding)
            if math.isinf(distance):
                continue
            record = {
                "image_rowid": data.get("image_rowid") or doc_id,
                "distance": distance,
                "description": data.get("description"),
                "album_title": data.get("album_title"),
                "timestamp": data.get("timestamp"),
                "thumb_path": data.get("thumb_path"),
                "thumb_url": data.get("thumb_url"),
                "file_path": data.get("file_path"),
                "image_url": data.get("image_url"),
                "user_id": data.get("user_id"),
            }
            results.append(record)

        results.sort(key=lambda item: item["distance"])
        return results[:top_k]

    def get_image_paths(self, image_id: str | int) -> Tuple[Optional[str], Optional[str]]:
        """Return file paths for an image and its thumbnail, if present."""

        doc = self._get_image_document(image_id)
        if not doc:
            return None, None
        return doc.get("file_path"), doc.get("thumb_path")

    def get_image_blob(self, image_id: str | int, prefer_thumb: bool = False) -> Tuple[Optional[bytes], Optional[str]]:
        """Return raw image bytes and mime type for ``image_id``.

        When ``prefer_thumb`` is ``True`` the thumbnail is returned if available.
        """

        doc = self._get_image_document(image_id)
        if not doc:
            return None, None

        mime_type = doc.get("mime_type", "image/jpeg")
        blob_key = "thumb_bytes" if prefer_thumb else "image_bytes"
        blob = doc.get(blob_key)

        if isinstance(blob, bytes):
            return blob, mime_type
        if isinstance(blob, str):
            try:
                return base64.b64decode(blob), mime_type
            except Exception:
                return blob.encode("utf-8"), mime_type

        path_key = "thumb_path" if prefer_thumb else "file_path"
        file_path = doc.get(path_key)
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as fh:
                return fh.read(), mime_type

        return None, mime_type

    # ------------------------------------------------------------------
    # User helpers (settings + credentials)
    # ------------------------------------------------------------------
    def get_user_settings(self, uid: str) -> dict:
        """Retrieves a user's settings."""

        if self._use_firestore:
            doc_ref = self.db.collection("users").document(uid)
            doc = doc_ref.get()
            if not doc.exists:
                return {}
            return doc.to_dict().get("settings", {})
        return self._local_users.get(uid, {}).get("settings", {})

    def save_user_settings(self, uid: str, settings: dict):
        """Saves a user's settings."""

        if self._use_firestore:
            doc_ref = self.db.collection("users").document(uid)
            doc_ref.set({"settings": settings}, merge=True)
        else:
            user_doc = self._local_users.setdefault(uid, {})
            user_doc["settings"] = settings

    def save_google_photos_credentials(self, uid: str, creds: Credentials):
        """Saves Google Photos credentials for a user."""

        creds_dict = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }

        if self._use_firestore:
            doc_ref = self.db.collection("users").document(uid)
            doc_ref.set({"google_photos_credentials": creds_dict}, merge=True)
        else:
            user_doc = self._local_users.setdefault(uid, {})
            user_doc["google_photos_credentials"] = creds_dict

    def get_google_photos_credentials(self, uid: str) -> Optional[Credentials]:
        """Retrieves Google Photos credentials for a user."""

        if self._use_firestore:
            doc_ref = self.db.collection("users").document(uid)
            doc = doc_ref.get()
            if not doc.exists:
                return None
            creds_dict = doc.to_dict().get("google_photos_credentials")
        else:
            creds_dict = self._local_users.get(uid, {}).get("google_photos_credentials")

        if not creds_dict:
            return None
        return Credentials(**creds_dict)

    def save_user_info(self, uid: str, user_info: dict):
        """Saves user info (like email)."""

        if self._use_firestore:
            doc_ref = self.db.collection("users").document(uid)
            doc_ref.set({"user_info": user_info}, merge=True)
        else:
            user_doc = self._local_users.setdefault(uid, {})
            user_doc["user_info"] = user_info

    def get_user_info(self, uid: str) -> dict:
        """Retrieves stored user info."""

        if self._use_firestore:
            doc_ref = self.db.collection("users").document(uid)
            doc = doc_ref.get()
            if not doc.exists:
                return {}
            return doc.to_dict().get("user_info", {})
        return self._local_users.get(uid, {}).get("user_info", {})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _iter_image_documents(self, user_id: Optional[str]) -> Iterable[Tuple[str, Dict[str, Any]]]:
        if self._use_firestore:
            collection = self.db.collection(self._IMAGES_COLLECTION)
            for doc in collection.stream():
                data = doc.to_dict() or {}
                if user_id and data.get("user_id") not in (None, user_id):
                    continue
                yield doc.id, data
        else:
            for image_id, data in self._local_images.items():
                if user_id and data.get("user_id") not in (None, user_id):
                    continue
                yield image_id, data

    def _get_image_document(self, image_id: str | int) -> Optional[Dict[str, Any]]:
        key = str(image_id)
        if self._use_firestore:
            doc = self.db.collection(self._IMAGES_COLLECTION).document(key).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            data.setdefault("image_rowid", key)
            return data
        return self._local_images.get(key)

    @staticmethod
    def _cosine_distance(vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return math.inf

        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return math.inf
        cosine = dot / (norm1 * norm2)
        return 1 - cosine


