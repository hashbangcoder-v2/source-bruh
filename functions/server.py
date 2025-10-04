import datetime
import hashlib
import io
import json
import os
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Response, Depends
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


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
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
    album_url: str = ""
    album_title: Optional[str] = None
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


def _split_album_source(value: Optional[str]) -> tuple[str, str]:
    """Returns ``(album_path, album_title)`` from user-provided ``value``."""

    raw = (value or "").strip()
    if not raw:
        return "", ""

    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        parsed = None

    looks_like_url = bool(parsed and parsed.scheme and parsed.netloc)
    looks_like_path = "/" in raw and not any(ch.isspace() for ch in raw)

    if looks_like_url or looks_like_path:
        return _normalize_album_path(raw), ""

    return "", raw


def create_app(config_path: str = None) -> FastAPI:
    config_file = Path(config_path) if config_path else Path(__file__).with_name("config.yaml")
    cfg = load_config(os.fspath(config_file))
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1", "chrome-extension://*", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    cfg_path = os.environ.get("SOURCE_BRUH_CONFIG") or os.fspath(config_file)
    db = FirestoreDB(cfg["db"]["service_account_key_path"])
    photos_client = GooglePhotosClient(cfg["google_photos"], db)
    gemini_client: GeminiClient | None = None
    storage_cfg = cfg.get("storage", {})
    images_dir = storage_cfg.get("images_dir", "data/images")
    thumbs_dir = storage_cfg.get("thumbs_dir", "data/thumbs")
    
    def get_gemini() -> GeminiClient | None:
        nonlocal gemini_client
        if gemini_client is not None:
            return gemini_client
        try:
            gemini_client = GeminiClient(
                api_key_env=cfg["llm"]["api_key_env"],
                oracle_model=cfg["llm"]["oracle_model"],
                embedding_model=cfg["llm"]["embedding_model"],
            )
            return gemini_client
        except Exception:
            return None

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True}

    @app.get("/search", response_model=List[SearchResponseItem])
    async def search(q: str, top_k: int = 20, user: dict = Depends(get_current_user)):
        if not q:
            raise HTTPException(status_code=400, detail="Missing query")
        client = get_gemini()
        if client is None:
            raise HTTPException(status_code=400, detail="Gemini API key not set. Update it in Settings.")
        emb = client.embed_text(q)
        rows = db.search(emb, top_k=top_k, user_id=user.get("uid"))
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
        return results

    @app.get("/image/{image_rowid}")
    def get_image(image_rowid: str, thumb: int = 0):
        blob, mime_type = db.get_image_blob(image_rowid, prefer_thumb=thumb == 1)
        if blob is None:
            raise HTTPException(status_code=404, detail="Image not found")
        return Response(content=blob, media_type=mime_type or "image/jpeg")

    @app.get("/settings", response_model=SettingsResponse, response_model_exclude_none=True)
    async def get_settings(user: dict = Depends(get_current_user)):
        """Endpoint to get user settings."""
        uid = user["uid"]
        user_settings = db.get_user_settings(uid) or {}
        album_url = (user_settings.get("album_url") or "").strip()
        album_title = (user_settings.get("album_title") or "").strip()

        if hasattr(db, "get_secret"):
            stored_secret = db.get_secret(uid, "gemini_api_key")
        else:
            stored_secret = user_settings.get("gemini_api_key")
        gemini_key_set = bool(stored_secret)
        if user_settings.get("gemini_key_set") != gemini_key_set:
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
            db.save_user_info(uid, {"email": email})

        return SettingsResponse(
            email=email,
            album_url=album_url,
            album_title=album_title or None,
            gemini_key_set=gemini_key_set,
        )


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
        album_path, album_title = _split_album_source(body.album_url)
        user_id = user["uid"]
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                current = json.load(f)
        except FileNotFoundError:
            current = {}
        photos_cfg = current.setdefault("google_photos", {})
        if album_path:
            photos_cfg["album_url"] = album_path
            photos_cfg["album_paths"] = [album_path]
            photos_cfg["albums"] = []
        else:
            photos_cfg["album_url"] = ""
            photos_cfg["album_paths"] = []
            photos_cfg["albums"] = [album_title] if album_title else []
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        cfg.setdefault("google_photos", {})["album_url"] = album_path
        cfg["google_photos"]["album_paths"] = [album_path] if album_path else []
        cfg["google_photos"]["albums"] = [album_title] if album_title else []

        existing = db.get_user_settings(user_id) or {}
        if album_path:
            existing["album_url"] = album_path
            existing.pop("album_title", None)
        elif album_title:
            existing["album_title"] = album_title
            existing.pop("album_url", None)
        else:
            existing.pop("album_url", None)
            existing.pop("album_title", None)
        if hasattr(db, "save_user_settings"):
            db.save_user_settings(user_id, existing)

        email = user.get("email")
        if email and hasattr(db, "save_user_info"):
            db.save_user_info(user_id, {"email": email})

        return {"ok": True, "album_url": album_path, "album_title": album_title}

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
        token_user_id = user["uid"]
        if not body.image_url:
            raise HTTPException(status_code=400, detail="Missing image URL")

        email = user.get("email")
        if email and hasattr(db, "save_user_info"):
            db.save_user_info(token_user_id, {"email": email})

        try:
            resp = requests.get(body.image_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download image: {exc}") from exc

        image_bytes = resp.content
        ensure_dirs(images_dir, thumbs_dir)
        sha = hashlib.sha256(image_bytes).hexdigest()
        filename = f"context-{sha[:16]}.jpg"
        file_path = os.path.join(images_dir, filename)
        thumb_path = os.path.join(thumbs_dir, filename)

        with open(file_path, "wb") as fh:
            fh.write(image_bytes)
        thumb_bytes = create_thumbnail(image_bytes)
        with open(thumb_path, "wb") as fh:
            fh.write(thumb_bytes)

        width = height = None
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                width, height = img.size
        except Exception:
            width = height = None

        client = get_gemini()
        if client is None:
            raise HTTPException(status_code=400, detail="Gemini API key not set. Update it in Settings.")

        description = client.describe_image(image_bytes)
        embedding = client.embed_text(description) if description else []

        timestamp = datetime.datetime.now(datetime.timezone.utc)

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

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    cfg = load_config(os.environ.get("SOURCE_BRUH_CONFIG") or None)
    host = cfg.get("server", {}).get("host", "127.0.0.1")
    port = int(cfg.get("server", {}).get("port", 5057))
    uvicorn.run("backend.src.server:app", host=host, port=port, reload=False)

