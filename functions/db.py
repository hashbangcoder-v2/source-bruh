import firebase_admin
from firebase_admin import credentials, firestore
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials

class FirestoreDB:
    def __init__(self, service_account_key_path: str):
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_key_path)
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def add_image_data(self, user_id: str, image_data: Dict[str, Any]):
        # Store image data in a user-specific collection
        self.db.collection('users').document(user_id).collection('images').add(image_data)

    def search_vectors(self, user_id: str, query_vector: List[float], top_k: int) -> List[Dict[str, Any]]:
        # This is a simplified search. For production, you'd use a dedicated vector search service
        # or Firestore's upcoming vector search capabilities.
        images_ref = self.db.collection('users').document(user_id).collection('images')
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


