import argparse
import datetime
import hashlib
import mimetypes
import os
import sys
from pathlib import Path
from typing import Iterable

from firebase_admin import storage
from PIL import Image

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
FUNCTIONS_ROOT = SCRIPT_PATH.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(FUNCTIONS_ROOT))

from config_loader import load_config
from db import FirestoreDB
from ingest import create_thumbnail
from llm import GeminiClient


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(folder: Path) -> Iterable[Path]:
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def resolve_config_path(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return FUNCTIONS_ROOT / "config.yaml"


def resolve_service_account(config_path: Path, service_account: str) -> Path:
    path = Path(service_account)
    if not path.is_absolute():
        path = config_path.parent / path
    return path


def image_dimensions(image_bytes: bytes) -> tuple[int | None, int | None]:
    try:
        from io import BytesIO

        with Image.open(BytesIO(image_bytes)) as img:
            return img.size
    except Exception:
        return None, None


def list_users(db: FirestoreDB) -> None:
    for doc in db.db.collection("users").stream():
        data = doc.to_dict() or {}
        info = data.get("user_info") or {}
        email = info.get("email") or ""
        name = info.get("name") or info.get("display_name") or ""
        print(f"{doc.id}\t{name}\t{email}")


def verify_storage_bucket(bucket_name: str) -> None:
    """Fail fast before Gemini calls if the configured bucket is missing."""

    bucket = storage.bucket(bucket_name)
    marker = bucket.blob("_sourcebruh_import_preflight/check.txt")
    marker.upload_from_string("ok", content_type="text/plain")
    marker.delete()


def main() -> int:
    parser = argparse.ArgumentParser(description="One-time local image import into SourceBruh.")
    parser.add_argument("--folder", help="Folder containing local images to index.")
    parser.add_argument("--user-id", help="Firebase uid to index images under.")
    parser.add_argument("--config", help="Path to functions/config.yaml.")
    parser.add_argument("--collection", default=None, help="Firestore image subcollection. Defaults to config db.image_collection.")
    parser.add_argument("--bucket", default=None, help="Firebase Storage bucket. Defaults to config storage.bucket_name.")
    parser.add_argument("--api-key-env", default=None, help="Environment variable containing Gemini API key.")
    parser.add_argument("--source-type", default="local-import", help="source_type metadata value.")
    parser.add_argument("--limit", type=int, default=None, help="Only import the first N images.")
    parser.add_argument("--reindex", action="store_true", help="Overwrite docs that already exist by sha256 image id.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect files and existing docs without Gemini/Storage writes.")
    parser.add_argument("--list-users", action="store_true", help="Print known Firestore users and exit.")
    parser.add_argument("--skip-bucket-check", action="store_true", help="Skip the write-mode Cloud Storage preflight check.")
    parser.add_argument("--yes", action="store_true", help="Required for writes to the prod collection/bucket.")
    args = parser.parse_args()

    config_path = resolve_config_path(args.config)
    cfg = load_config(str(config_path))
    db_cfg = cfg.get("db", {})
    llm_cfg = cfg.get("llm", {})
    storage_cfg = cfg.get("storage", {})

    service_account = resolve_service_account(config_path, db_cfg["service_account_key_path"])
    image_collection = args.collection or db_cfg.get("image_collection") or "images"
    bucket_name = args.bucket or storage_cfg.get("bucket_name") or storage_cfg.get("bucket")

    if not bucket_name:
        raise SystemExit("Missing Firebase Storage bucket. Set --bucket or storage.bucket_name.")

    db = FirestoreDB(
        str(service_account),
        image_collection=image_collection,
        storage_bucket=bucket_name,
    )

    if args.list_users:
        list_users(db)
        return 0

    if not args.folder:
        raise SystemExit("--folder is required unless --list-users is used.")
    if not args.user_id:
        raise SystemExit("--user-id is required unless --list-users is used.")

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        raise SystemExit(f"Folder does not exist or is not a directory: {folder}")

    image_paths = list(iter_images(folder))
    if args.limit is not None:
        image_paths = image_paths[: args.limit]
    if not image_paths:
        raise SystemExit(f"No images found under {folder}")

    print(f"Folder: {folder}")
    print(f"User: {args.user_id}")
    print(f"Collection: users/{args.user_id}/{image_collection}")
    print(f"Bucket: {bucket_name}")
    print(f"Images discovered: {len(image_paths)}")

    if not args.dry_run and not args.yes:
        raise SystemExit("Refusing to write without --yes. Run --dry-run first, then add --yes.")

    api_key = None
    gemini = None
    if not args.dry_run:
        if not args.skip_bucket_check:
            try:
                verify_storage_bucket(bucket_name)
            except Exception as exc:
                raise SystemExit(
                    f"Storage bucket preflight failed for {bucket_name}: {exc}"
                ) from exc

        env_name = args.api_key_env or llm_cfg.get("api_key_env") or "GOOGLE_API_KEY"
        api_key = os.environ.get(env_name) or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise SystemExit(
                f"Missing Gemini API key. Set {env_name}, GEMINI_API_KEY, or GOOGLE_API_KEY in this shell."
            )
        gemini = GeminiClient(
            api_key=api_key,
            embedding_model=llm_cfg.get("embedding_model", "gemini-embedding-2"),
            output_dimensionality=int(db_cfg.get("dimension", 768)),
        )

    run_id = datetime.datetime.now(datetime.timezone.utc).isoformat()
    imported = 0
    skipped = 0
    failed = 0

    for index, image_path in enumerate(image_paths, start=1):
        try:
            image_bytes = image_path.read_bytes()
            sha = hashlib.sha256(image_bytes).hexdigest()
            media_id = sha
            mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"

            if not args.reindex and db.has_media_item(args.user_id, media_id):
                skipped += 1
                print(f"[{index}/{len(image_paths)}] skip existing {image_path.name} {sha[:12]}")
                continue

            if args.dry_run:
                print(f"[{index}/{len(image_paths)}] would import {image_path.name} {len(image_bytes)} bytes {sha[:12]}")
                continue

            assert gemini is not None
            embedding = gemini.embed_image(image_bytes, mime_type)
            thumb_bytes = create_thumbnail(image_bytes)
            storage_refs = db.store_image_blobs(
                args.user_id,
                media_id,
                image_bytes,
                thumb_bytes,
                mime_type,
            )
            width, height = image_dimensions(image_bytes)
            now = datetime.datetime.now(datetime.timezone.utc)

            db.upsert_media_item(
                args.user_id,
                media_id,
                {
                    "image_id": media_id,
                    "timestamp": now,
                    "timestamp_iso": now.isoformat(),
                    "created_at": now,
                    "updated_at": now,
                    "sha256": sha,
                    "description": "",
                    "user_description": "",
                    "embedding": embedding,
                    "embedding_kind": "image",
                    "embedding_model": llm_cfg.get("embedding_model", "gemini-embedding-2"),
                    "embedding_dim": len(embedding),
                    "mime_type": mime_type,
                    "filename": image_path.name,
                    "source_url": image_path.as_posix(),
                    "source_type": args.source_type,
                    "manual_entry": True,
                    "width": width,
                    "height": height,
                    "import_run_id": run_id,
                    **storage_refs,
                },
            )
            imported += 1
            print(f"[{index}/{len(image_paths)}] imported {image_path.name} {sha[:12]}")
        except Exception as exc:
            failed += 1
            print(f"[{index}/{len(image_paths)}] FAILED {image_path}: {exc}", file=sys.stderr)

    print(f"Summary: imported={imported} skipped={skipped} failed={failed} dry_run={args.dry_run}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
