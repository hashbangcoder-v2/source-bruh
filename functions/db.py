import datetime
from typing import Any, Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2.credentials import Credentials


class FirestoreDB:
    def __init__(self, service_account_key_path: str):
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_key_path)
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def _images_collection(self, user_id: str):
        return self.db.collection('users').document(user_id).collection('images')

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
        # This is a simplified search. For production, you'd use a dedicated vector search service
        # or Firestore's upcoming vector search capabilities.
        images_ref = self._images_collection(user_id)
        all_images = images_ref.stream()

        # This is a placeholder for actual vector search logic
        # In a real app, you would not pull all documents and compare locally.
        results = []
        for img in all_images:
            img_dict = img.to_dict()
            # Faking distance calculation
            img_dict['distance'] = 0.5 
            results.append(img_dict)

        return sorted(results, key=lambda x: x['distance'])[:top_k]
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


