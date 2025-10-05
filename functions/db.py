import base64
import datetime
import math
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2.credentials import Credentials
from logger_config import get_logger, log_exception

logger = get_logger(__name__)


class FirestoreDB:
    def __init__(self, service_account_key_path: str):
        logger.info(f"🔥 Initializing Firestore database")
        logger.debug(f"Service account key: {service_account_key_path}")
        
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_key_path)
                firebase_admin.initialize_app(cred)
                logger.debug("✓ Firebase Admin SDK initialized")
            else:
                logger.debug("Firebase Admin SDK already initialized")
            
            self.db = firestore.client()
            logger.info(f"✓ Firestore client connected")
        except Exception as e:
            log_exception(logger, "Failed to initialize Firestore", e)
            raise
        
        self._use_firestore = True
        self._local_users: Dict[str, Dict[str, Any]] = {}
        self._local_images: Dict[str, Dict[str, Any]] = {}
        self._IMAGES_COLLECTION = "images"

    def _images_collection(self, user_id: str):
        return self.db.collection('users').document(user_id).collection('images')

    def _secrets_collection(self, user_id: str):
        return self.db.collection('users').document(user_id).collection('secrets')

    def add_image_data(self, user_id: str, image_data: Dict[str, Any]):
        media_id = image_data.get('google_media_id')
        if media_id:
            self.upsert_media_item(user_id, media_id, image_data)
            return
        # Store image data in a user-specific collection when no explicit id is provided
        self._images_collection(user_id).add(image_data)

    def has_media_item(self, user_id: str, media_id: str) -> bool:
        doc = self._images_collection(user_id).document(media_id).get()
        return doc.exists

    def upsert_media_item(self, user_id: str, media_id: str, image_data: Dict[str, Any]) -> str:
        payload = dict(image_data)
        payload['google_media_id'] = media_id
        doc_ref = self._images_collection(user_id).document(media_id)
        doc_ref.set(payload, merge=True)
        return doc_ref.id

    def get_latest_media_timestamp(self, user_id: str, album_title: Optional[str] = None) -> Optional[datetime.datetime]:
        collection = self._images_collection(user_id)
        query = collection
        if album_title:
            query = query.where('album_title', '==', album_title)
        try:
            docs = (
                query.order_by('timestamp', direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream()
            )
        except Exception:
            return None
        for doc in docs:
            data = doc.to_dict() or {}
            ts = data.get('timestamp')
            if isinstance(ts, datetime.datetime):
                return ts
            if isinstance(ts, str):
                try:
                    return datetime.datetime.fromisoformat(ts)
                except ValueError:
                    continue
        return None

    def search_vectors(self, user_id: str, query_vector: List[float], top_k: int) -> List[Dict[str, Any]]:
        """
        Performs vector similarity search against stored image embeddings.
        
        Note: This is a simplified in-memory implementation. For production scale,
        consider using Vertex AI Vector Search, Pinecone, or similar services.
        
        Args:
            user_id: User ID to scope the search
            query_vector: Query embedding vector
            top_k: Number of top results to return
            
        Returns:
            List of image documents sorted by distance (most similar first)
        """
        images_ref = self._images_collection(user_id)
        all_images = images_ref.stream()

        results = []
        for img in all_images:
            img_dict = img.to_dict()
            embedding = img_dict.get('embedding', [])
            
            if not embedding:
                continue
                
            # Calculate cosine distance
            distance = self._cosine_distance(query_vector, embedding)
            img_dict['distance'] = distance
            img_dict['image_rowid'] = img.id
            results.append(img_dict)

        return sorted(results, key=lambda x: x['distance'])[:top_k]
    
    def search(self, query_embedding: List[float], top_k: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Main search interface called by server endpoints.
        
        Args:
            query_embedding: Query vector to search for
            top_k: Number of results to return
            user_id: User ID to scope search to specific user's images
            
        Returns:
            List of image documents with distance scores
        """
        logger.info(f"🔍 Searching images (top_k={top_k}, user={user_id})")
        
        if not user_id:
            logger.error("✗ user_id is required for search")
            raise ValueError("user_id is required for search")
        
        try:
            results = self.search_vectors(user_id, query_embedding, top_k)
            logger.info(f"✓ Search completed: found {len(results)} results")
            return results
        except Exception as e:
            log_exception(logger, f"Search failed for user {user_id}", e)
            raise
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

    def save_secret(self, uid: str, name: str, value: str):
        """Persists a sensitive secret value under a dedicated sub-collection."""

        if self._use_firestore:
            doc_ref = self._secrets_collection(uid).document(name)
            doc_ref.set({"value": value, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        else:
            user_doc = self._local_users.setdefault(uid, {})
            secrets = user_doc.setdefault("secrets", {})
            secrets[name] = {"value": value}

    def get_secret(self, uid: str, name: str) -> Optional[str]:
        """Retrieves a previously stored secret value."""

        if self._use_firestore:
            doc_ref = self._secrets_collection(uid).document(name)
            doc = doc_ref.get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            return data.get("value")

        secrets = self._local_users.get(uid, {}).get("secrets", {})
        stored = secrets.get(name)
        if isinstance(stored, dict):
            return stored.get("value")
        return stored

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


