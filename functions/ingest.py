import io
import os
from typing import List

from PIL import Image

from config_loader import load_config
from db import Database
from photos_client import GooglePhotosClient
from llm import GeminiClient


def create_thumbnail(image_bytes: bytes, max_size: int = 320) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_size, max_size))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def ensure_dirs(*dirs: List[str]) -> None:
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def ingest_once(config_path: str = None) -> None:
    cfg = load_config(config_path)

    images_dir = cfg["storage"]["images_dir"]
    thumbs_dir = cfg["storage"]["thumbs_dir"]
    ensure_dirs(images_dir, thumbs_dir)

    db = Database(cfg["db"]["path"], cfg["db"]["dimension"])
    photos = GooglePhotosClient(
        client_secret_path=cfg["google_photos"]["client_secret_path"],
        scopes=cfg["google_photos"]["scopes"],
        redirect_port=cfg["google_photos"]["redirect_port"],
        token_store=cfg["google_photos"].get("token_store"),
    )
    gemini = GeminiClient(
        api_key_env=cfg["llm"]["api_key_env"],
        oracle_model=cfg["llm"]["oracle_model"],
        embedding_model=cfg["llm"]["embedding_model"],
    )

    albums = cfg["google_photos"].get("albums", [])
    max_size = cfg["storage"]["max_download_size"]

    for album_title in albums:
        album = photos.get_album_by_title(album_title)
        if not album:
            continue
        album_id = album["id"]
        for item in photos.iter_media_items_in_album(album_id):
            if not item.get("mimeType", "").startswith("image/"):
                continue
            media_id = item.get("id")
            if media_id and db.has_image_by_media_id(media_id):
                continue

            base_url = item.get("baseUrl")
            filename = item.get("filename", f"{media_id}.jpg")
            timestamp = item.get("mediaMetadata", {}).get("creationTime")
            width = int(item.get("mediaMetadata", {}).get("width", 0) or 0)
            height = int(item.get("mediaMetadata", {}).get("height", 0) or 0)

            image_bytes = photos.download_image_bytes(base_url, max_size)
            thumb_bytes = create_thumbnail(image_bytes)

            file_path = os.path.join(images_dir, filename)
            thumb_path = os.path.join(thumbs_dir, filename)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            with open(thumb_path, "wb") as f:
                f.write(thumb_bytes)

            description = gemini.describe_image(image_bytes)
            embedding = gemini.embed_text(description)

            rowid = db.upsert_image(
                google_media_id=media_id,
                album_title=album_title,
                file_path=file_path,
                thumb_path=thumb_path,
                timestamp=timestamp,
                width=width,
                height=height,
                sha256=None,
                description=description,
            )
            db.insert_or_replace_vector(rowid, embedding)


if __name__ == "__main__":
    ingest_once()


