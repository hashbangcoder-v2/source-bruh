import argparse
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, storage

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
FUNCTIONS_ROOT = SCRIPT_PATH.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(FUNCTIONS_ROOT))

from config_loader import load_config


def resolve_config_path(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return FUNCTIONS_ROOT / "config.yaml"


def resolve_service_account(config_path: Path, service_account: str) -> Path:
    path = Path(service_account)
    if not path.is_absolute():
        path = config_path.parent / path
    return path


def copy_blob(src_bucket_name: str, dst_bucket_name: str, blob_path: str, *, dry_run: bool) -> None:
    if not blob_path:
        return
    src_bucket = storage.bucket(src_bucket_name)
    dst_bucket = storage.bucket(dst_bucket_name)
    src_blob = src_bucket.blob(blob_path)
    if dry_run:
        return
    src_bucket.copy_blob(src_blob, dst_bucket, blob_path)


def clone_collection(
    *,
    db,
    user_id: str,
    src_collection: str,
    dst_collection: str,
    src_bucket: str,
    dst_bucket: str,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    src_ref = db.collection("users").document(user_id).collection(src_collection)
    dst_ref = db.collection("users").document(user_id).collection(dst_collection)

    copied = 0
    skipped = 0
    failed = 0

    docs = list(src_ref.stream())
    print(f"Source docs discovered: {len(docs)}")

    for doc in docs:
        try:
            data = doc.to_dict() or {}
            dst_doc = dst_ref.document(doc.id)
            if not overwrite and dst_doc.get().exists:
                skipped += 1
                print(f"skip existing {dst_collection}/{doc.id}")
                continue

            source_bucket = data.get("storage_bucket") or src_bucket
            paths = {
                data.get("original_storage_path") or data.get("storage_path"),
                data.get("thumb_storage_path"),
            }
            for blob_path in sorted(path for path in paths if path):
                copy_blob(source_bucket, dst_bucket, blob_path, dry_run=dry_run)

            cloned = dict(data)
            cloned["storage_bucket"] = dst_bucket
            cloned["cloned_from_collection"] = src_collection
            cloned["cloned_from_bucket"] = source_bucket
            cloned["cloned_to_collection"] = dst_collection
            cloned["cloned_to_bucket"] = dst_bucket
            cloned["cloned_at"] = firestore.SERVER_TIMESTAMP

            if not dry_run:
                dst_doc.set(cloned)

            copied += 1
            print(f"copied {src_collection}/{doc.id} -> {dst_collection}/{doc.id}")
        except Exception as exc:
            failed += 1
            print(f"FAILED {src_collection}/{doc.id}: {exc}", file=sys.stderr)

    return copied, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone SourceBruh image docs and blobs without Gemini calls.")
    parser.add_argument("--config", help="Path to functions/config.yaml.")
    parser.add_argument("--user-id", required=True, help="Firebase uid whose image collections should be cloned.")
    parser.add_argument("--src-collection", required=True)
    parser.add_argument("--dst-collection", required=True)
    parser.add_argument("--src-bucket", required=True)
    parser.add_argument("--dst-bucket", required=True)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination docs.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned copies without writing.")
    parser.add_argument("--yes", action="store_true", help="Required for writes.")
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        raise SystemExit("Refusing to write without --yes. Run --dry-run first, then add --yes.")

    config_path = resolve_config_path(args.config)
    cfg = load_config(str(config_path))
    service_account = resolve_service_account(config_path, cfg["db"]["service_account_key_path"])

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(service_account)))

    db = firestore.client()
    copied, skipped, failed = clone_collection(
        db=db,
        user_id=args.user_id,
        src_collection=args.src_collection,
        dst_collection=args.dst_collection,
        src_bucket=args.src_bucket,
        dst_bucket=args.dst_bucket,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )

    print(f"Summary: copied={copied} skipped={skipped} failed={failed} dry_run={args.dry_run}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
