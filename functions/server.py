from typing import Any, Dict, List, Optional
import json
import os

from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from pydantic import BaseModel

from config_loader import load_config
from db import FirestoreDB
from llm import GeminiClient
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from photos_client import GooglePhotosClient


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


class SearchResponseItem(BaseModel):
    image_rowid: int
    distance: float
    description: Optional[str]
    album_title: Optional[str]
    timestamp: Optional[str]
    thumb_url: str

class SettingsResponse(BaseModel):
    email: str
    album_url: str
    gemini_key_set: bool


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
    db = FirestoreDB(cfg["db"]["service_account_key_path"])
    photos_client = GooglePhotosClient(cfg["google_photos"], db)
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
    async def search(q: str, top_k: int = 20, user: dict = Depends(get_current_user)):
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

    @app.get("/settings", response_model=SettingsResponse)
    async def get_settings(user: dict = Depends(get_current_user)):
        """Endpoint to get user settings."""
        uid = user["uid"]
        user_settings = db.get_user_settings(uid)
        if not user_settings:
            raise HTTPException(status_code=404, detail="Settings not found for user")

        user_info = photos_client.get_user_info_from_db(uid)

        return SettingsResponse(
            email=user_info.get("email", ""),
            album_url=user_settings.get("album_url", ""),
            gemini_key_set=bool(user_settings.get("gemini_api_key")),
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

