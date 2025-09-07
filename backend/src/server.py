from typing import Any, Dict, List, Optional
import json
import os

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.src.config_loader import load_config
from backend.src.db import Database
from backend.src.llm import GeminiClient
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from backend.src.photos_client import GooglePhotosClient


class SearchResponseItem(BaseModel):
    image_rowid: int
    distance: float
    description: Optional[str]
    album_title: Optional[str]
    timestamp: Optional[str]
    thumb_url: str


def create_app(config_path: str = None) -> FastAPI:
    cfg = load_config(config_path)
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1", "chrome-extension://*", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    cfg_path = os.environ.get("SOURCE_BRUH_CONFIG") or os.fspath(__import__("pathlib").Path.cwd() / "backend" / "config.yaml")
    db = Database(cfg["db"]["path"], cfg["db"]["dimension"])
    gemini_client: GeminiClient | None = None

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
    def search(q: str, top_k: int = 20):
        if not q:
            raise HTTPException(status_code=400, detail="Missing query")
        client = get_gemini()
        if client is None:
            raise HTTPException(status_code=400, detail="Gemini API key not set. Update it in Settings.")
        emb = client.embed_text(q)
        rows = db.search(emb, top_k=top_k)
        base_thumb = "/image/{}?thumb=1"
        results: List[SearchResponseItem] = []
        for r in rows:
            results.append(
                SearchResponseItem(
                    image_rowid=int(r["image_rowid"]),
                    distance=float(r["distance"]),
                    description=r["description"],
                    album_title=r["album_title"],
                    timestamp=r["timestamp"],
                    thumb_url=base_thumb.format(int(r["image_rowid"]))
                )
            )
        return results

    @app.get("/image/{image_rowid}")
    def get_image(image_rowid: int, thumb: int = 0):
        file_path, thumb_path = db.get_image_paths(image_rowid)
        target = thumb_path if thumb == 1 and thumb_path else file_path
        if not target or not os.path.exists(target):
            raise HTTPException(status_code=404, detail="Image not found")
        with open(target, "rb") as f:
            data = f.read()
        return Response(content=data, media_type="image/jpeg")

    @app.get("/settings")
    def get_settings():
        # Load latest config from disk so UI reflects updates immediately
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                current_cfg = json.load(f)
        except Exception:
            current_cfg = cfg
        # Redact API key
        llm_cfg = dict(current_cfg.get("llm", {}))
        key_env = llm_cfg.get("api_key_env")
        key_present = True if key_env and os.environ.get(key_env) else False
        # Try to get user info from token store
        user_email = None
        token_store = current_cfg.get("google_photos", {}).get("token_store")
        if token_store and os.path.exists(token_store):
            try:
                with open(token_store, "r", encoding="utf-8") as f:
                    data = json.load(f)
                creds = Credentials.from_authorized_user_info(data)
                oauth2 = build('oauth2', 'v2', credentials=creds)
                info = oauth2.userinfo().get().execute()
                user_email = info.get("email")
            except Exception:
                user_email = None
        return {
            "user": user_email,
            "albums": current_cfg.get("google_photos", {}).get("albums", []),
            "album_url": current_cfg.get("google_photos", {}).get("album_url", ""),
            "gemini_key_present": key_present,
            "gemini_key_env": key_env,
        }

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
    def update_album_url(body: UpdateAlbumUrlBody):
        with open(cfg_path, "r", encoding="utf-8") as f:
            current = json.load(f)
        current.setdefault("google_photos", {})["album_url"] = body.album_url
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        # Update in-memory cfg as well
        cfg.setdefault("google_photos", {})["album_url"] = body.album_url
        return {"ok": True}

    class UpdateGeminiKeyBody(BaseModel):
        api_key: str

    @app.post("/settings/gemini-key")
    def update_gemini_key(body: UpdateGeminiKeyBody):
        key_env = cfg["llm"]["api_key_env"]
        os.environ[key_env] = body.api_key
        return {"ok": True}

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
        # Trigger OAuth flow to ensure credentials and update token store
        photos_cfg = cfg.get("google_photos", {})
        client = GooglePhotosClient(
            client_secret_path=photos_cfg.get("client_secret_path"),
            scopes=photos_cfg.get("scopes", []),
            redirect_port=photos_cfg.get("redirect_port", 1008),
            token_store=photos_cfg.get("token_store"),
            oauth_client=photos_cfg.get("oauth_client"),
        )
        return {"ok": True, "user": client.user_email}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    cfg = load_config(os.environ.get("SOURCE_BRUH_CONFIG") or None)
    host = cfg.get("server", {}).get("host", "127.0.0.1")
    port = int(cfg.get("server", {}).get("port", 5057))
    uvicorn.run("backend.src.server:app", host=host, port=port, reload=False)

