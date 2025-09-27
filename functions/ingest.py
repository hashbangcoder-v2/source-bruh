import datetime
import hashlib
import io
import os
import urllib.parse
from typing import Iterable, List, Optional

from PIL import Image

try:  # pragma: no cover - allow running as module or script
    from .config_loader import load_config
    from .db import FirestoreDB
    from .photos_client import GooglePhotosClient
    from .llm import GeminiClient
except ImportError:  # pragma: no cover
    from config_loader import load_config
    from db import FirestoreDB
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


def _coerce_list(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        return [values]
    return [v for v in values if v]


def _normalize_album_path(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return raw
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return raw.lstrip("/")
    if parsed.scheme and parsed.netloc:
        path = parsed.path.rstrip("/")
        return path.lstrip("/")
    return raw.lstrip("/")


def _parse_creation_time(value: Optional[str]) -> Optional[datetime.datetime]:
    if not value:
        return None
    try:
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def ingest_once(
    config_path: Optional[str] = None,
    *,
    db: Optional[FirestoreDB] = None,
    photos_client: Optional[GooglePhotosClient] = None,
    gemini_client: Optional[GeminiClient] = None,
    user_id: Optional[str] = None,
) -> None:
    cfg = load_config(config_path)

    storage_cfg = cfg.get("storage", {})
    images_dir = storage_cfg.get("images_dir", "data/images")
    thumbs_dir = storage_cfg.get("thumbs_dir", "data/thumbs")
    ensure_dirs(images_dir, thumbs_dir)

    db_cfg = cfg.get("db", {})
    resolved_user_id = user_id or db_cfg.get("user_id") or "default"

    if db is None:
        service_account = db_cfg.get("service_account_key_path")
        if not service_account:
            raise RuntimeError("Firestore service account key path must be configured under db.service_account_key_path")
        db = FirestoreDB(service_account)

    photos_cfg = cfg.get("google_photos", {})
    if photos_client is None:
        photos_client = GooglePhotosClient(
            client_secret_path=photos_cfg.get("client_secret_path"),
            scopes=photos_cfg.get("scopes", []),
            redirect_port=int(photos_cfg.get("redirect_port", 1008)),
            token_store=photos_cfg.get("token_store"),
            oauth_client=photos_cfg.get("oauth_client"),
            db=db,
            user_id=resolved_user_id,
        )

    if gemini_client is None:
        llm_cfg = cfg.get("llm", {})
        gemini_client = GeminiClient(
            api_key_env=llm_cfg.get("api_key_env", "GOOGLE_API_KEY"),
            oracle_model=llm_cfg.get("oracle_model", "gemini-1.5-flash-latest"),
            embedding_model=llm_cfg.get("embedding_model", "text-embedding-004"),
        )

    max_size = storage_cfg.get("max_download_size", "w2048-h2048")

    album_paths = []
    for raw in _coerce_list(photos_cfg.get("album_paths")):
        normalized = _normalize_album_path(raw)
        if normalized:
            album_paths.append(normalized)
    for raw in _coerce_list(photos_cfg.get("album_url")):
        normalized = _normalize_album_path(raw)
        if normalized:
            album_paths.append(normalized)

    album_entries: List[tuple[dict, Optional[str]]] = []
    for album_path in album_paths:
        album = photos_client.get_album_by_path(album_path)
        if album:
            album_entries.append((album, album_path))

    fallback_titles = _coerce_list(photos_cfg.get("albums", []))
    for album_title in fallback_titles:
        album = photos_client.get_album_by_title(album_title)
        if album:
            album_entries.append((album, None))

    seen_albums: set[str] = set()
    for album, configured_path in album_entries:
        album_id = album.get("id")
        if not album_id or album_id in seen_albums:
            continue
        seen_albums.add(album_id)
        album_title = album.get("title")
        last_timestamp: Optional[datetime.datetime] = None
        if hasattr(db, "get_latest_media_timestamp"):
            try:
                last_timestamp = db.get_latest_media_timestamp(resolved_user_id, album_title=album_title)
            except Exception:
                last_timestamp = None

        product_url = album.get("productUrl", "")
        product_path = _normalize_album_path(product_url) if product_url else None

        for item in photos_client.iter_media_items_in_album(album_id):
            if not item.get("mimeType", "").startswith("image/"):
                continue

            media_id = item.get("id")
            if not media_id:
                continue

            if hasattr(db, "has_media_item") and db.has_media_item(resolved_user_id, media_id):
                continue

            base_url = item.get("baseUrl")
            if not base_url:
                continue

            filename = item.get("filename") or f"{media_id}.jpg"
            metadata = item.get("mediaMetadata", {}) or {}
            timestamp_raw = metadata.get("creationTime")
            timestamp_dt = _parse_creation_time(timestamp_raw)
            if timestamp_dt is None:
                timestamp_dt = datetime.datetime.fromtimestamp(0, datetime.timezone.utc)
            if last_timestamp and timestamp_dt <= last_timestamp:
                continue
            width = int(metadata.get("width", 0) or 0)
            height = int(metadata.get("height", 0) or 0)

            image_bytes = photos_client.download_image_bytes(base_url, max_size)
            thumb_bytes = create_thumbnail(image_bytes)

            file_path = os.path.join(images_dir, filename)
            thumb_path = os.path.join(thumbs_dir, filename)
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            with open(thumb_path, "wb") as f:
                f.write(thumb_bytes)

            description = gemini_client.describe_image(image_bytes) if gemini_client else ""
            embedding = gemini_client.embed_text(description) if gemini_client and description else []

            db.upsert_media_item(
                resolved_user_id,
                media_id,
                {
                    "google_media_id": media_id,
                    "album_title": album_title,
                    "album_path": configured_path or product_path,
                    "album_product_url": product_url,
                    "file_path": file_path,
                    "thumb_path": thumb_path,
                    "timestamp": timestamp_dt,
                    "timestamp_iso": timestamp_raw,
                    "width": width,
                    "height": height,
                    "sha256": hashlib.sha256(image_bytes).hexdigest(),
                    "description": description,
                    "embedding": embedding,
                    "mime_type": item.get("mimeType"),
                    "filename": filename,
                    "source_base_url": base_url,
                    "image_bytes": image_bytes,
                    "thumbnail_bytes": thumb_bytes,
                },
            )

            if last_timestamp is None or timestamp_dt > last_timestamp:
                last_timestamp = timestamp_dt


if __name__ == "__main__":
    ingest_once()


