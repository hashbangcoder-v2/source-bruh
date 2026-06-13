import datetime
import hashlib
import io
import json
import os
import re
import time
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional
# from firebase import functions

from fastapi import FastAPI, HTTPException, Response, Depends, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from pydantic import BaseModel
import requests

from config_loader import load_config
from db import FirestoreDB
from llm import GeminiClient
from ingest import create_thumbnail, ensure_dirs
from photos_client import GooglePhotosClient
from PIL import Image
from logger_config import get_logger, log_exception

# Initialize logger
logger = get_logger(__name__)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Verify Firebase ID token and return user information."""
    try:
        # Development bypass 
        if os.getenv("SKIP_AUTH") == "true":
            logger.warning("⚠️  Auth bypassed - development mode only!")
            return {"uid": "dev-user", "email": "dev@example.com"}
        else:
            decoded_token = auth.verify_id_token(token)
            user_id = decoded_token.get("uid")
            logger.debug(f"✓ Authenticated user: {user_id}")
            return decoded_token
    except Exception as e:
        logger.warning(f"✗ Authentication failed: {e.__class__.__name__}: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


class SearchResponseItem(BaseModel):
    image_rowid: str
    distance: float
    description: Optional[str]
    album_title: Optional[str]
    timestamp: Optional[str]
    thumb_url: str

class SettingsResponse(BaseModel):
    email: str
    album_url: str
    gemini_key_set: bool

class AddImageBody(BaseModel):
    image_url: str
    page_url: Optional[str] = None
    album_path: Optional[str] = None
    album_title: Optional[str] = None
    user_description: Optional[str] = None

class ResolveImageBody(BaseModel):
    image_url: str
    page_url: Optional[str] = None
    album_path: Optional[str] = None
    album_title: Optional[str] = None

class CommitPreviewBody(BaseModel):
    preview_id: str
    user_description: Optional[str] = None


class PreviewImageParser(HTMLParser):
    """Extract common social preview image metadata from a shared page."""

    def __init__(self) -> None:
        super().__init__()
        self.image_url: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if self.image_url or tag.lower() != "meta":
            return
        values = {key.lower(): value for key, value in attrs if value is not None}
        name = (values.get("property") or values.get("name") or "").lower()
        if name in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            self.image_url = values.get("content")


def _normalize_album_path(value: Optional[str]) -> str:
    if not value:
        return ""
    raw = value.strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return raw.strip("/")
    if parsed.scheme and parsed.netloc:
        path = parsed.path.strip("/")
        return path
    return raw.strip("/")


def create_app(config_path: str = None) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    This function:
    1. Loads configuration from config.yaml
    2. Initializes Firebase/Firestore connections
    3. Sets up CORS middleware
    4. Registers all API endpoints
    5. Creates singleton clients for Photos and Gemini APIs
    
    Args:
        config_path: Path to config.yaml (optional, defaults to ./config.yaml)
        
    Returns:
        Configured FastAPI application instance
    """
    logger.info("🚀 Initializing Source-Bruh Backend API")
    
    config_file = Path(config_path) if config_path else Path(__file__).with_name("config.yaml")
    logger.info(f"📁 Loading config from: {config_file}")
    
    try:
        cfg = load_config(os.fspath(config_file))
        logger.info("✓ Configuration loaded successfully")
    except Exception as e:
        logger.error(f"✗ Failed to load configuration: {e}")
        raise
    
    app = FastAPI(title="Source-Bruh Backend API", version="1.0.0")

    logger.info("🔧 Configuring CORS middleware")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1", "chrome-extension://*", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    cfg_path = os.environ.get("SOURCE_BRUH_CONFIG") or os.fspath(config_file)
    
    logger.info("🔥 Initializing Firestore database connection")
    try:
        db = FirestoreDB(cfg["db"]["service_account_key_path"])
        logger.info("✓ Firestore connected successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize Firestore: {e}")
        raise
    
    logger.info("📸 Initializing Google Photos client")
    try:
        photos_client = GooglePhotosClient(cfg["google_photos"], db)
        logger.info("✓ Google Photos client initialized")
    except Exception as e:
        logger.warning(f"⚠ Google Photos client initialization issue: {e}")
        photos_client = GooglePhotosClient(cfg["google_photos"], db)
    
    # Cache Gemini clients per user (for user-specific API keys)
    gemini_clients: Dict[str, GeminiClient] = {}
    # Global fallback client (for shared/admin API key from secrets)
    global_gemini_client: GeminiClient | None = None
    
    storage_cfg = cfg.get("storage", {})
    images_dir = storage_cfg.get("images_dir", "data/images")
    thumbs_dir = storage_cfg.get("thumbs_dir", "data/thumbs")
    pending_dir = storage_cfg.get("pending_dir", "data/pending")
    logger.info(f"💾 Storage: images={images_dir}, thumbs={thumbs_dir}")
    
    def get_api_key_from_secrets() -> Optional[str]:
        """
        Retrieve Gemini API key from Firebase Secrets or environment variables.
        
        Priority:
        1. GEMINI_API_KEY environment variable (set by Firebase Secrets in production)
        2. GOOGLE_API_KEY environment variable (legacy/local)
        
        Returns:
            API key string or None if not found
        """
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            logger.debug("✓ Found API key in environment (from Firebase Secrets)")
        return api_key
    
    def get_gemini(user_id: Optional[str] = None) -> GeminiClient | None:
        """
        Get or create Gemini client for the specified user.
        
        Best practices implementation:
        1. Connection Pooling: Reuse clients globally
        2. Caching: Store clients per user in memory
        3. Lazy Loading: Initialize only when needed
        
        Priority for API key retrieval:
        1. User-specific key from Firestore (if user_id provided)
        2. Global key from Firebase Secrets/environment
        
        Args:
            user_id: User ID to fetch user-specific API key (optional)
            
        Returns:
            GeminiClient instance or None if no API key available
        """
        nonlocal gemini_clients, global_gemini_client
        
        api_key = None
        
        # Try to get user-specific API key from Firestore
        if user_id:
            # Check cache first
            if user_id in gemini_clients:
                logger.debug(f"✓ Using cached Gemini client for user: {user_id}")
                return gemini_clients[user_id]
            
            # Try to load from Firestore
            try:
                logger.debug(f"🔍 Fetching user-specific API key for: {user_id}")
                user_settings = db.get_user_settings(user_id)
                api_key = user_settings.get("gemini_api_key")
                if api_key:
                    logger.info(f"✓ Using user-specific API key for: {user_id}")
            except Exception as e:
                logger.debug(f"⚠ Could not fetch user settings: {e}")
        
        # Fallback to global API key from secrets
        if not api_key:
            api_key = get_api_key_from_secrets()
            if api_key:
                logger.debug("✓ Using global API key from Firebase Secrets")
                # Return cached global client if available
                if global_gemini_client is not None:
                    return global_gemini_client
        
        if not api_key:
            logger.warning("✗ No API key available (check user settings or Firebase Secrets)")
            return None
        
        # Initialize new client
        logger.info(f"🤖 Initializing Gemini client" + (f" for user: {user_id}" if user_id else " (global)"))
        try:
            client = GeminiClient(
                api_key=api_key,
                oracle_model=cfg["llm"]["oracle_model"],
                embedding_model=cfg["llm"]["embedding_model"],
            )
            
            # Cache the client
            if user_id:
                gemini_clients[user_id] = client
            else:
                global_gemini_client = client
            
            logger.info("✓ Gemini client initialized successfully")
            return client
        except Exception as e:
            logger.error(f"✗ Failed to initialize Gemini client: {e}")
            return None

    def download_shared_image(image_url: str) -> tuple[bytes, str, str]:
        """Download a direct image URL or resolve a page's preview image."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 "
                "(KHTML, like Gecko) SourceBruh/1.0"
            )
        }

        try:
            resp = requests.get(image_url, timeout=30, headers=headers)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log_exception(logger, f"Failed to download shared URL {image_url}", exc)
            raise HTTPException(status_code=400, detail=f"Failed to download image: {exc}") from exc

        content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        if content_type.startswith("image/"):
            return resp.content, content_type, resp.url

        if "html" not in content_type:
            raise HTTPException(
                status_code=400,
                detail=f"Shared URL is not an image (content type: {content_type or 'unknown'}).",
            )

        parser = PreviewImageParser()
        parser.feed(resp.text[:500_000])
        if not parser.image_url:
            raise HTTPException(
                status_code=400,
                detail="Shared page did not expose a preview image. Try sharing the image file directly.",
            )

        preview_url = urllib.parse.urljoin(resp.url, parser.image_url)
        try:
            image_resp = requests.get(preview_url, timeout=30, headers=headers)
            image_resp.raise_for_status()
        except requests.RequestException as exc:
            log_exception(logger, f"Failed to download preview image {preview_url}", exc)
            raise HTTPException(status_code=400, detail=f"Failed to download preview image: {exc}") from exc

        image_content_type = (
            image_resp.headers.get("Content-Type") or ""
        ).split(";", 1)[0].lower()
        if not image_content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Preview URL is not an image (content type: {image_content_type or 'unknown'}).",
            )

        return image_resp.content, image_content_type, image_resp.url

    def _safe_preview_id(value: str) -> str:
        return re.sub(r"[^a-fA-F0-9]", "", value)[:64]

    def _pending_paths(preview_id: str) -> tuple[str, str, str]:
        safe_id = _safe_preview_id(preview_id)
        return (
            os.path.join(pending_dir, f"{safe_id}.img"),
            os.path.join(pending_dir, f"{safe_id}.thumb.jpg"),
            os.path.join(pending_dir, f"{safe_id}.json"),
        )

    def save_pending_image(
        *,
        user_id: str,
        image_bytes: bytes,
        mime_type: Optional[str],
        source_url: Optional[str],
        page_url: Optional[str],
        album_path: Optional[str],
        album_title: Optional[str],
        source_type: str,
    ) -> Dict[str, Any]:
        os.makedirs(pending_dir, exist_ok=True)
        sha = hashlib.sha256(image_bytes).hexdigest()
        image_path, thumb_path, meta_path = _pending_paths(sha)
        try:
            with open(image_path, "wb") as fh:
                fh.write(image_bytes)
            thumb_bytes = create_thumbnail(image_bytes)
            with open(thumb_path, "wb") as fh:
                fh.write(thumb_bytes)
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "preview_id": sha,
                        "user_id": user_id,
                        "mime_type": mime_type,
                        "source_url": source_url,
                        "page_url": page_url,
                        "album_path": album_path,
                        "album_title": album_title,
                        "source_type": source_type,
                        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    },
                    fh,
                    indent=2,
                )
        except Exception as e:
            log_exception(logger, "Failed to save pending preview image", e)
            raise HTTPException(status_code=500, detail=f"Failed to prepare image preview: {str(e)}")

        return {
            "ok": True,
            "preview_id": sha,
            "preview_url": app.url_path_for("get_preview_image", preview_id=sha),
            "resolved_image_url": source_url,
            "mime_type": mime_type,
        }

    def load_pending_image(preview_id: str, user_id: str) -> tuple[bytes, Dict[str, Any]]:
        safe_id = _safe_preview_id(preview_id)
        if not safe_id:
            raise HTTPException(status_code=400, detail="Invalid preview id")
        image_path, _, meta_path = _pending_paths(safe_id)
        if not os.path.exists(image_path) or not os.path.exists(meta_path):
            raise HTTPException(status_code=404, detail="Preview image expired or was not found")
        with open(meta_path, "r", encoding="utf-8") as fh:
            metadata = json.load(fh)
        if metadata.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Preview image belongs to another user")
        with open(image_path, "rb") as fh:
            return fh.read(), metadata

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all incoming requests and their response times."""
        start_time = time.time()
        path = request.url.path
        method = request.method 
        
        logger.info(f"⬅  {method} {path}")
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code < 400:
                logger.info(f"➡  {method} {path} → {response.status_code} ({duration_ms:.2f}ms)")
            else:
                logger.warning(f"➡  {method} {path} → {response.status_code} ({duration_ms:.2f}ms)")
            
            return response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"➡  {method} {path} → ERROR ({duration_ms:.2f}ms): {e}")
            raise

    @app.get("/health")
    def health() -> Dict[str, Any]:
        """Health check endpoint."""
        logger.debug("💓 Health check")
        return {"ok": True}

    @app.get("/search", response_model=List[SearchResponseItem])
    async def search(q: str, top_k: int = 20, user: dict = Depends(get_current_user)):
        """Search for images using semantic similarity."""
        user_id = user.get("uid")
        logger.info(f"🔍 Search query: '{q}' (top_k={top_k}, user={user_id})")
        
        if not q:
            logger.warning("✗ Empty search query")
            raise HTTPException(status_code=400, detail="Missing query")
        
        client = get_gemini(user_id=user_id)
        if client is None:
            logger.error("✗ Gemini client not available")
            raise HTTPException(status_code=400, detail="Gemini API key not set. Update it in Settings.")
        
        try:
            logger.debug(f"🧮 Generating embedding for: '{q}'")
            emb = client.embed_text(q)
            logger.debug(f"✓ Embedding generated (dim={len(emb)})")
        except Exception as e:
            log_exception(logger, "Failed to generate embedding", e)
            raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")
        
        try:
            logger.debug(f"🗄️  Searching database (top_k={top_k})")
            rows = db.search(emb, top_k=top_k, user_id=user_id)
            logger.info(f"✓ Found {len(rows)} results")
        except Exception as e:
            log_exception(logger, "Database search failed", e)
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
        
        results: List[SearchResponseItem] = []
        for r in rows:
            image_id = str(r.get("image_rowid"))
            thumb_url = r.get("thumb_url") or ""
            if not thumb_url:
                if r.get("thumb_path") or r.get("thumb_bytes"):
                    thumb_url = app.url_path_for("get_image", image_rowid=image_id) + "?thumb=1"
                elif r.get("image_url"):
                    thumb_url = str(r["image_url"])
            results.append(
                SearchResponseItem(
                    image_rowid=image_id,
                    distance=float(r["distance"]),
                    description=r.get("description"),
                    album_title=r.get("album_title"),
                    timestamp=r.get("timestamp"),
                    thumb_url=thumb_url,
                )
            )
        
        logger.info(f"✓ Returning {len(results)} search results")
        return results

    @app.get("/image/{image_rowid}")
    def get_image(image_rowid: str, thumb: int = 0):
        """Retrieve image or thumbnail by ID."""
        img_type = "thumbnail" if thumb == 1 else "full image"
        logger.debug(f"🖼️  Retrieving {img_type}: {image_rowid}")
        
        try:
            blob, mime_type = db.get_image_blob(image_rowid, prefer_thumb=thumb == 1)
            if blob is None:
                logger.warning(f"✗ Image not found: {image_rowid}")
                raise HTTPException(status_code=404, detail="Image not found")
            
            logger.debug(f"✓ Returning {img_type} ({len(blob)} bytes, {mime_type})")
            return Response(content=blob, media_type=mime_type or "image/jpeg")
        except HTTPException:
            raise
        except Exception as e:
            log_exception(logger, f"Failed to retrieve image {image_rowid}", e)
            raise HTTPException(status_code=500, detail=f"Image retrieval failed: {str(e)}")

    @app.get("/settings", response_model=SettingsResponse)
    async def get_settings(user: dict = Depends(get_current_user)):
        """Endpoint to get user settings."""
        uid = user["uid"]
        logger.info(f"⚙️  Fetching settings for user: {uid}")
        
        try:
            user_settings = db.get_user_settings(uid) or {}
            if not isinstance(user_settings, dict):
                logger.warning(f"Unexpected settings payload for user {uid}: {type(user_settings).__name__}")
                user_settings = {}
            album_url = str(user_settings.get("album_url") or "")

            stored_secret = None
            try:
                if hasattr(db, "get_secret"):
                    stored_secret = db.get_secret(uid, "gemini_api_key")
                else:
                    stored_secret = user_settings.get("gemini_api_key")
            except Exception as secret_error:
                logger.warning(f"Could not read Gemini key state for user {uid}: {secret_error}")
            gemini_key_set = bool(stored_secret)
            
            if user_settings.get("gemini_key_set") != gemini_key_set:
                logger.debug(f"Updating gemini_key_set flag for user {uid}")
                user_settings["gemini_key_set"] = gemini_key_set
                if hasattr(db, "save_user_settings"):
                    db.save_user_settings(uid, user_settings)

            if hasattr(db, "get_user_info"):
                stored_user = db.get_user_info(uid) or {}
            elif hasattr(photos_client, "get_user_info_from_db"):
                stored_user = photos_client.get_user_info_from_db(uid) or {}
            else:
                stored_user = {}
            if not isinstance(stored_user, dict):
                stored_user = {}
            
            email = str(user.get("email") or stored_user.get("email") or "")
            if email and stored_user.get("email") != email and hasattr(db, "save_user_info"):
                logger.debug(f"Updating email for user {uid}")
                db.save_user_info(uid, {"email": email})

            logger.info(f"✓ Settings retrieved for {email} (album_url={'set' if album_url else 'not set'}, gemini_key={'set' if gemini_key_set else 'not set'})")
            
            return SettingsResponse(
                email=email,
                album_url=album_url,
                gemini_key_set=gemini_key_set,
            )
        except Exception as e:
            log_exception(logger, "Failed to fetch settings", e)
            raise HTTPException(status_code=500, detail=f"Settings retrieval failed: {str(e)}")


    class UpdateAlbumsBody(BaseModel):
        albums: List[str]

    @app.post("/settings/albums")
    def update_albums(body: UpdateAlbumsBody):
        # Persist albums in config.json
        cfg_path = os.environ.get("SOURCE_BRUH_CONFIG", os.path.join(os.getcwd(), "config.json"))
        with open(cfg_path, "r", encoding="utf-8") as f:
            current = json.load(f)
        current.setdefault("google_photos", {})["albums"] = body.albums
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        return {"ok": True}

    class UpdateAlbumUrlBody(BaseModel):
        album_url: str

    @app.post("/settings/album-url")
    def update_album_url(body: UpdateAlbumUrlBody, user: dict = Depends(get_current_user)):
        normalized = _normalize_album_path(body.album_url)
        user_id = user["uid"]
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except FileNotFoundError:
            current = {}
        photos_cfg = current.setdefault("google_photos", {})
        photos_cfg["album_url"] = normalized
        photos_cfg["album_paths"] = [normalized] if normalized else []
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        cfg.setdefault("google_photos", {})["album_url"] = normalized
        cfg["google_photos"]["album_paths"] = [normalized] if normalized else []

        existing = db.get_user_settings(user_id) or {}
        existing["album_url"] = normalized
        if hasattr(db, "save_user_settings"):
            db.save_user_settings(user_id, existing)

        email = user.get("email")
        if email and hasattr(db, "save_user_info"):
            db.save_user_info(user_id, {"email": email})

        return {"ok": True, "album_url": normalized}

    class UpdateGeminiKeyBody(BaseModel):
        api_key: str

    @app.post("/settings/gemini-key")
    def update_gemini_key(body: UpdateGeminiKeyBody, user: dict = Depends(get_current_user)):
        api_key = (body.api_key or "").strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")

        key_env = cfg["llm"]["api_key_env"]
        os.environ[key_env] = api_key

        user_id = user["uid"]
        nonlocal global_gemini_client
        gemini_clients.pop(user_id, None)
        global_gemini_client = None
        existing = db.get_user_settings(user_id) or {}
        if hasattr(db, "save_secret"):
            db.save_secret(user_id, "gemini_api_key", api_key)
        else:
            existing["gemini_api_key"] = api_key
        existing["gemini_key_set"] = True
        if hasattr(db, "save_user_settings"):
            db.save_user_settings(user_id, existing)

        email = user.get("email")
        if email and hasattr(db, "save_user_info"):
            db.save_user_info(user_id, {"email": email})

        return {"ok": True}

    def index_image_bytes(
        *,
        token_user_id: str,
        image_bytes: bytes,
        mime_type: Optional[str],
        source_url: Optional[str],
        page_url: Optional[str],
        album_path: Optional[str],
        album_title: Optional[str],
        source_type: str,
    ) -> Dict[str, Any]:
        """Index image bytes supplied by mobile uploads or downloaded URLs."""
        ensure_dirs(images_dir, thumbs_dir)
        sha = hashlib.sha256(image_bytes).hexdigest()
        filename = f"{source_type}-{sha[:16]}.jpg"
        file_path = os.path.join(images_dir, filename)
        thumb_path = os.path.join(thumbs_dir, filename)

        try:
            with open(file_path, "wb") as fh:
                fh.write(image_bytes)
            thumb_bytes = create_thumbnail(image_bytes)
            with open(thumb_path, "wb") as fh:
                fh.write(thumb_bytes)
        except Exception as e:
            log_exception(logger, "Failed to save image files", e)
            raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

        width = height = None
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                width, height = img.size
        except Exception as e:
            logger.warning(f"Could not determine image dimensions: {e}")

        client = get_gemini(user_id=token_user_id)
        if client is None:
            raise HTTPException(status_code=400, detail="Gemini API key not set. Update it in Settings.")

        try:
            description = client.describe_image(image_bytes)
            user_note = (user_description or "").strip()
            if user_note:
                description = f"{description}\n\nUser note: {user_note}" if description else user_note
            embedding = client.embed_text(description) if description else []
        except Exception as e:
            log_exception(logger, "Failed to generate description/embedding", e)
            raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

        timestamp = datetime.datetime.now(datetime.timezone.utc)

        try:
            db.upsert_media_item(
                token_user_id,
                sha,
                {
                    "google_media_id": sha,
                    "album_title": album_title,
                    "album_path": album_path,
                    "file_path": file_path,
                    "thumb_path": thumb_path,
                    "timestamp": timestamp,
                    "timestamp_iso": timestamp.isoformat(),
                    "sha256": sha,
                    "description": description,
                    "embedding": embedding,
                    "mime_type": mime_type,
                    "filename": filename,
                    "source_base_url": source_url,
                    "image_bytes": image_bytes,
                    "thumbnail_bytes": thumb_bytes,
                    "width": width,
                    "height": height,
                    "manual_entry": True,
                    "source_type": source_type,
                    "source_page_url": page_url,
                    "user_description": (user_description or "").strip(),
                },
            )
        except Exception as e:
            log_exception(logger, "Failed to store image in database", e)
            raise HTTPException(status_code=500, detail=f"Database storage failed: {str(e)}")

        return {"ok": True, "media_id": sha}

    @app.post("/images/upload")
    async def upload_image(
        file: UploadFile = File(...),
        page_url: str = Form(""),
        album_path: str = Form("android-share"),
        album_title: str = Form("Android share"),
        user_description: str = Form(""),
        user: dict = Depends(get_current_user),
    ):
        """Index an image uploaded directly from the Android sharesheet."""
        token_user_id = user["uid"]
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image uploads are supported")

        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image was empty")

        email = user.get("email")
        if email and hasattr(db, "save_user_info"):
            db.save_user_info(token_user_id, {"email": email})

        return index_image_bytes(
            token_user_id=token_user_id,
            image_bytes=image_bytes,
            mime_type=file.content_type,
            source_url=file.filename,
            page_url=page_url or None,
            album_path=album_path or None,
            album_title=album_title or file.filename,
            source_type="android-share",
            user_description=user_description,
        )

    @app.post("/images/resolve-url")
    def resolve_image_url(body: ResolveImageBody, user: dict = Depends(get_current_user)):
        """Download a shared URL and prepare a preview before the user indexes it."""
        token_user_id = user["uid"]
        logger.info(f"Resolving shared URL preview for user {token_user_id}")
        logger.debug(f"Shared URL: {body.image_url}")

        if not body.image_url:
            raise HTTPException(status_code=400, detail="Missing image URL")

        image_bytes, mime_type, resolved_image_url = download_shared_image(body.image_url)
        logger.info(
            f"Prepared shared image preview ({len(image_bytes)} bytes, {mime_type}) from {resolved_image_url}"
        )
        return save_pending_image(
            user_id=token_user_id,
            image_bytes=image_bytes,
            mime_type=mime_type,
            source_url=resolved_image_url,
            page_url=body.page_url or body.image_url,
            album_path=body.album_path,
            album_title=body.album_title or "Shared URL",
            source_type="context-menu",
        )

    @app.get("/images/preview/{preview_id}", name="get_preview_image")
    def get_preview_image(preview_id: str, thumb: int = 1):
        """Return a pending preview image. Preview URLs are transient local-test artifacts."""
        safe_id = _safe_preview_id(preview_id)
        if not safe_id:
            raise HTTPException(status_code=400, detail="Invalid preview id")
        image_path, thumb_path, meta_path = _pending_paths(safe_id)
        if not os.path.exists(meta_path):
            raise HTTPException(status_code=404, detail="Preview image not found")
        path = thumb_path if thumb == 1 and os.path.exists(thumb_path) else image_path
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Preview image not found")
        try:
            with open(meta_path, "r", encoding="utf-8") as fh:
                metadata = json.load(fh)
            mime_type = "image/jpeg" if path == thumb_path else metadata.get("mime_type") or "image/jpeg"
            with open(path, "rb") as fh:
                return Response(content=fh.read(), media_type=mime_type)
        except Exception as e:
            log_exception(logger, f"Failed to serve preview image {preview_id}", e)
            raise HTTPException(status_code=500, detail=f"Preview image failed: {str(e)}")

    @app.post("/images/commit-preview")
    def commit_preview_image(body: CommitPreviewBody, user: dict = Depends(get_current_user)):
        """Index a previously resolved preview image after user confirmation."""
        token_user_id = user["uid"]
        image_bytes, metadata = load_pending_image(body.preview_id, token_user_id)
        result = index_image_bytes(
            token_user_id=token_user_id,
            image_bytes=image_bytes,
            mime_type=metadata.get("mime_type"),
            source_url=metadata.get("source_url"),
            page_url=metadata.get("page_url"),
            album_path=metadata.get("album_path"),
            album_title=metadata.get("album_title") or "Shared URL",
            source_type=metadata.get("source_type") or "context-menu",
            user_description=body.user_description,
        )
        logger.info(f"Committed preview image {body.preview_id[:16]} for user {token_user_id}")
        return result

    @app.post("/images/from-url")
    def add_image_from_url(body: AddImageBody, user: dict = Depends(get_current_user)):
        """Add and index an image from a URL (context menu feature)."""
        token_user_id = user["uid"]
        logger.info(f"📥 Adding image from URL for user {token_user_id}")
        logger.debug(f"Image URL: {body.image_url}")
        logger.debug(f"Page URL: {body.page_url}")
        
        if not body.image_url:
            logger.warning("✗ Missing image URL")
            raise HTTPException(status_code=400, detail="Missing image URL")

        email = user.get("email")
        if email and hasattr(db, "save_user_info"):
            db.save_user_info(token_user_id, {"email": email})

        image_bytes, mime_type, resolved_image_url = download_shared_image(body.image_url)
        logger.info(f"Downloaded shared image ({len(image_bytes)} bytes) from {resolved_image_url}")
        return index_image_bytes(
            token_user_id=token_user_id,
            image_bytes=image_bytes,
            mime_type=mime_type,
            source_url=resolved_image_url,
            page_url=body.page_url or body.image_url,
            album_path=body.album_path,
            album_title=body.album_title or "Shared URL",
            source_type="context-menu",
        )

        email = user.get("email")
        if email and hasattr(db, "save_user_info"):
            db.save_user_info(token_user_id, {"email": email})

        logger.debug(f"🌐 Downloading image from: {body.image_url}")
        try:
            resp = requests.get(body.image_url, timeout=30)
            resp.raise_for_status()
            logger.info(f"✓ Image downloaded ({len(resp.content)} bytes)")
        except requests.RequestException as exc:
            log_exception(logger, f"Failed to download image from {body.image_url}", exc)
            raise HTTPException(status_code=400, detail=f"Failed to download image: {exc}") from exc

        image_bytes = resp.content
        ensure_dirs(images_dir, thumbs_dir)
        sha = hashlib.sha256(image_bytes).hexdigest()
        filename = f"context-{sha[:16]}.jpg"
        file_path = os.path.join(images_dir, filename)
        thumb_path = os.path.join(thumbs_dir, filename)

        logger.debug(f"💾 Saving image: {filename} (SHA256: {sha[:16]}...)")
        try:
            with open(file_path, "wb") as fh:
                fh.write(image_bytes)
            thumb_bytes = create_thumbnail(image_bytes)
            with open(thumb_path, "wb") as fh:
                fh.write(thumb_bytes)
            logger.debug(f"✓ Saved full image and thumbnail")
        except Exception as e:
            log_exception(logger, "Failed to save image files", e)
            raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

        width = height = None
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                width, height = img.size
                logger.debug(f"📐 Image dimensions: {width}x{height}")
        except Exception as e:
            logger.warning(f"⚠ Could not determine image dimensions: {e}")
            width = height = None

        client = get_gemini(user_id=token_user_id)
        if client is None:
            logger.error("✗ Gemini client not available for image description")
            raise HTTPException(status_code=400, detail="Gemini API key not set. Update it in Settings.")

        logger.info(f"🤖 Generating description and embedding")
        try:
            description = client.describe_image(image_bytes)
            logger.debug(f"✓ Description generated ({len(description)} chars)")
            embedding = client.embed_text(description) if description else []
            logger.debug(f"✓ Embedding generated (dim={len(embedding)})")
        except Exception as e:
            log_exception(logger, "Failed to generate description/embedding", e)
            raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

        timestamp = datetime.datetime.now(datetime.timezone.utc)

        logger.debug(f"🗄️  Storing image metadata in database")
        try:
            db.upsert_media_item(
                token_user_id,
                sha,
                {
                    "google_media_id": sha,
                    "album_title": body.album_title,
                    "album_path": body.album_path,
                    "file_path": file_path,
                    "thumb_path": thumb_path,
                    "timestamp": timestamp,
                    "timestamp_iso": timestamp.isoformat(),
                    "sha256": sha,
                    "description": description,
                    "embedding": embedding,
                    "mime_type": resp.headers.get("Content-Type"),
                    "filename": filename,
                    "source_base_url": body.image_url,
                    "image_bytes": image_bytes,
                    "thumbnail_bytes": thumb_bytes,
                    "width": width,
                    "height": height,
                    "manual_entry": True,
                    "source_type": "context-menu",
                    "source_page_url": body.page_url,
                },
            )
            logger.info(f"✓ Image added successfully: {sha[:16]}... from {body.page_url or 'unknown page'}")
        except Exception as e:
            log_exception(logger, "Failed to store image in database", e)
            raise HTTPException(status_code=500, detail=f"Database storage failed: {str(e)}")

        return {"ok": True, "media_id": sha}

    @app.post("/settings/logout")
    def logout():
        token_store = cfg.get("google_photos", {}).get("token_store")
        if token_store and os.path.exists(token_store):
            try:
                os.remove(token_store)
            except Exception:
                pass
        return {"ok": True}

    @app.post("/auth/login")
    def login():
        auth_url = photos_client.get_auth_url()
        return {"ok": True, "auth_url": auth_url}

    logger.info("✅ Source-Bruh Backend API initialized successfully")
    logger.info(
        "Endpoints: /health, /search, /settings, /images/upload, "
        "/images/resolve-url, /images/commit-preview, /images/from-url"
    )
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    logger.info("🎬 Starting uvicorn server")
    cfg = load_config(os.environ.get("SOURCE_BRUH_CONFIG") or None)
    host = cfg.get("server", {}).get("host", "127.0.0.1")
    port = int(cfg.get("server", {}).get("port", 5057))
    logger.info(f"🌐 Server will listen on http://{host}:{port}")
    uvicorn.run("backend.src.server:app", host=host, port=port, reload=False)

