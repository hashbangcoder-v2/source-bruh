import datetime
import hashlib
import io
import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Response, Depends, Request
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
    
    gemini_client: GeminiClient | None = None
    storage_cfg = cfg.get("storage", {})
    images_dir = storage_cfg.get("images_dir", "data/images")
    thumbs_dir = storage_cfg.get("thumbs_dir", "data/thumbs")
    logger.info(f"💾 Storage: images={images_dir}, thumbs={thumbs_dir}")
    
    def get_gemini() -> GeminiClient | None:
        nonlocal gemini_client
        if gemini_client is not None:
            return gemini_client
        logger.info("🤖 Initializing Gemini AI client")
        try:
            gemini_client = GeminiClient(
                api_key_env=cfg["llm"]["api_key_env"],
                oracle_model=cfg["llm"]["oracle_model"],
                embedding_model=cfg["llm"]["embedding_model"],
            )
            logger.info("✓ Gemini client initialized successfully")
            return gemini_client
        except Exception as e:
            logger.error(f"✗ Failed to initialize Gemini client: {e}")
            return None

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
        
        client = get_gemini()
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
            album_url = user_settings.get("album_url", "")

            if hasattr(db, "get_secret"):
                stored_secret = db.get_secret(uid, "gemini_api_key")
            else:
                stored_secret = user_settings.get("gemini_api_key")
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
            
            email = user.get("email") or stored_user.get("email", "")
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

        nonlocal gemini_client
        gemini_client = None

        user_id = user["uid"]
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

        client = get_gemini()
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
    logger.info(f"📝 Endpoints: /health, /search, /settings, /images/from-url")
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

