import firebase_admin
from firebase_admin import credentials, firestore
from typing import List, Dict, Any

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


