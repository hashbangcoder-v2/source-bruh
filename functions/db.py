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

    def get_user_settings(self, uid: str) -> dict:
        """Retrieves a user's settings from Firestore."""
        doc_ref = self.db.collection("users").document(uid)
        doc = doc_ref.get()
        if not doc.exists:
            return {}
        return doc.to_dict().get("settings", {})

    def save_user_settings(self, uid: str, settings: dict):
        """Saves a user's settings to Firestore."""
        doc_ref = self.db.collection("users").document(uid)
        doc_ref.set({"settings": settings}, merge=True)

    def save_google_photos_credentials(self, uid: str, creds: Credentials):
        """Saves Google Photos credentials to Firestore for a user."""
        doc_ref = self.db.collection("users").document(uid)
        creds_dict = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }
        doc_ref.set({"google_photos_credentials": creds_dict}, merge=True)

    def get_google_photos_credentials(self, uid: str) -> Optional[Credentials]:
        """Retrieves Google Photos credentials from Firestore for a user."""
        doc_ref = self.db.collection("users").document(uid)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        creds_dict = doc.to_dict().get("google_photos_credentials")
        if not creds_dict:
            return None

        return Credentials(**creds_dict)

    def save_user_info(self, uid: str, user_info: dict):
        """Saves user info (like email) to Firestore."""
        doc_ref = self.db.collection("users").document(uid)
        doc_ref.set({"user_info": user_info}, merge=True)

    def get_user_info(self, uid: str) -> dict:
        """Retrieves user info from Firestore."""
        doc_ref = self.db.collection("users").document(uid)
        doc = doc_ref.get()
        if not doc.exists:
            return {}
        return doc.to_dict().get("user_info", {})


