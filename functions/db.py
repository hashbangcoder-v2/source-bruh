import base64
import datetime
import math
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.oauth2.credentials import Credentials
from logger_config import get_logger, log_exception

logger = get_logger(__name__)


class FirestoreDB:
    def __init__(
        self,
        service_account_key_path: str,
        image_collection: str = "images",
        storage_bucket: Optional[str] = None,
    ):
        logger.info(f"🔥 Initializing Firestore database")
        logger.debug(f"Service account key: {service_account_key_path}")
        
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_key_path)
                options = {"storageBucket": storage_bucket} if storage_bucket else None
                firebase_admin.initialize_app(cred, options)
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
        self._IMAGES_COLLECTION = image_collection or "images"
        self._storage_bucket = storage_bucket

    def _images_collection(self, user_id: str):
        return self.db.collection('users').document(user_id).collection(self._IMAGES_COLLECTION)

    def _secrets_collection(self, user_id: str):
        return self.db.collection('users').document(user_id).collection('secrets')

    def _queries_collection(self, user_id: str):
        return self.db.collection('users').document(user_id).collection('queries')

    def add_image_data(self, user_id: str, image_data: Dict[str, Any]):
        media_id = image_data.get('image_id') or image_data.get('google_media_id')
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
        payload.setdefault('image_id', media_id)
        doc_ref = self._images_collection(user_id).document(media_id)
        doc_ref.set(payload)
        return doc_ref.id

    def store_image_blobs(
        self,
        user_id: str,
        image_id: str,
        image_bytes: bytes,
        thumbnail_bytes: bytes,
        mime_type: Optional[str] = None,
    ) -> Dict[str, str]:
        """Upload original and thumbnail bytes to Cloud Storage for Firebase."""

        bucket = storage.bucket(self._storage_bucket) if self._storage_bucket else storage.bucket()
        original_path = f"users/{user_id}/images/{image_id}/original"
        thumb_path = f"users/{user_id}/images/{image_id}/thumb.jpg"

        bucket.blob(original_path).upload_from_string(
            image_bytes,
            content_type=mime_type or "image/jpeg",
        )
        bucket.blob(thumb_path).upload_from_string(
            thumbnail_bytes,
            content_type="image/jpeg",
        )

        return {
            "storage_bucket": bucket.name,
            "storage_path": original_path,
            "original_storage_path": original_path,
            "thumb_storage_path": thumb_path,
        }

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

    def record_query_event(
        self,
        user_id: str,
        query: str,
        top_k: int,
        result_count: int,
    ) -> None:
        """Persist a lightweight successful-query event for profile stats."""

        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "query": query,
            "top_k": top_k,
            "result_count": result_count,
            "created_at": now,
            "created_at_iso": now.isoformat(),
        }
        if self._use_firestore:
            self._queries_collection(user_id).add(payload)
        else:
            user_doc = self._local_users.setdefault(user_id, {})
            user_doc.setdefault("queries", []).append(payload)

    def get_profile_stats(self, user_id: str) -> Dict[str, int]:
        """Return simple per-user profile counters."""

        now = datetime.datetime.now(datetime.timezone.utc)
        week_start = now - datetime.timedelta(days=7)
        files_indexed = 0
        queries_lifetime = 0
        queries_last_week = 0

        if self._use_firestore:
            for _ in self._images_collection(user_id).stream():
                files_indexed += 1
            for doc in self._queries_collection(user_id).stream():
                queries_lifetime += 1
                data = doc.to_dict() or {}
                created_at = data.get("created_at")
                if isinstance(created_at, datetime.datetime):
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                    if created_at >= week_start:
                        queries_last_week += 1
                elif isinstance(created_at, str):
                    try:
                        parsed = datetime.datetime.fromisoformat(created_at)
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                        if parsed >= week_start:
                            queries_last_week += 1
                    except ValueError:
                        pass
            return {
                "files_indexed": files_indexed,
                "queries_lifetime": queries_lifetime,
                "queries_last_week": queries_last_week,
            }

        files_indexed = sum(
            1
            for image in self._local_images.values()
            if image.get("user_id") in (None, user_id)
        )
        queries = self._local_users.get(user_id, {}).get("queries", [])
        queries_lifetime = len(queries)
        for query_event in queries:
            created_at = query_event.get("created_at")
            if isinstance(created_at, datetime.datetime):
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=datetime.timezone.utc)
                if created_at >= week_start:
                    queries_last_week += 1
        return {
            "files_indexed": files_indexed,
            "queries_lifetime": queries_lifetime,
            "queries_last_week": queries_last_week,
        }

    def get_image_blob(
        self,
        image_id: str | int,
        prefer_thumb: bool = False,
        user_id: Optional[str] = None,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """Return raw image bytes and mime type for ``image_id``.

        When ``prefer_thumb`` is ``True`` the thumbnail is returned if available.
        """

        doc = self._get_image_document(image_id, user_id=user_id)
        if not doc:
            return None, None

        mime_type = doc.get("mime_type", "image/jpeg")
        storage_path = doc.get("thumb_storage_path") if prefer_thumb else (
            doc.get("original_storage_path") or doc.get("storage_path")
        )
        if storage_path:
            bucket_name = doc.get("storage_bucket") or self._storage_bucket
            bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()
            blob = bucket.blob(storage_path)
            content_type = blob.content_type or ("image/jpeg" if prefer_thumb else mime_type)
            return blob.download_as_bytes(), content_type

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
            settings = (doc.to_dict() or {}).get("settings", {})
            return settings if isinstance(settings, dict) else {}
        settings = self._local_users.get(uid, {}).get("settings", {})
        return settings if isinstance(settings, dict) else {}

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
            user_info = (doc.to_dict() or {}).get("user_info", {})
            return user_info if isinstance(user_info, dict) else {}
        user_info = self._local_users.get(uid, {}).get("user_info", {})
        return user_info if isinstance(user_info, dict) else {}

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

    def _get_image_document(
        self,
        image_id: str | int,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        key = str(image_id)
        if self._use_firestore:
            if user_id:
                doc = self._images_collection(user_id).document(key).get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    data.setdefault("image_rowid", key)
                    return data

            doc = self.db.collection(self._IMAGES_COLLECTION).document(key).get()
            if doc.exists:
                data = doc.to_dict() or {}
                data.setdefault("image_rowid", key)
                return data

            matches = (
                self.db.collection_group(self._IMAGES_COLLECTION)
                .where("image_id", "==", key)
                .limit(1)
                .stream()
            )
            for match in matches:
                data = match.to_dict() or {}
                data.setdefault("image_rowid", match.id)
                return data

            matches = (
                self.db.collection_group(self._IMAGES_COLLECTION)
                .where("google_media_id", "==", key)
                .limit(1)
                .stream()
            )
            for match in matches:
                data = match.to_dict() or {}
                data.setdefault("image_rowid", match.id)
                return data

            return None
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


