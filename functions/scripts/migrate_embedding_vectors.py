import argparse
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
FUNCTIONS_ROOT = SCRIPT_PATH.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(FUNCTIONS_ROOT))

from config_loader import load_config
from db import FirestoreDB


def resolve_config_path(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return FUNCTIONS_ROOT / "config.yaml"


def resolve_service_account(config_path: Path, service_account: str) -> Path:
    path = Path(service_account)
    if not path.is_absolute():
        path = config_path.parent / path
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill Firestore native vector fields from existing embedding lists."
    )
    parser.add_argument("--user-id", required=True, help="Firebase uid to migrate.")
    parser.add_argument("--config", help="Path to functions/config.yaml.")
    parser.add_argument(
        "--collection",
        default=None,
        help="Firestore image subcollection. Defaults to config db.image_collection.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only scan the first N docs.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rewrite vector values even when the vector field already exists.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually write updates. Without this, the script is a dry run.",
    )
    args = parser.parse_args()

    config_path = resolve_config_path(args.config)
    cfg = load_config(str(config_path))
    db_cfg = cfg.get("db", {})
    storage_cfg = cfg.get("storage", {})

    service_account = resolve_service_account(config_path, db_cfg["service_account_key_path"])
    image_collection = args.collection or db_cfg.get("image_collection") or "images"
    vector_field = db_cfg.get("vector_field") or "embedding_vector"

    db = FirestoreDB(
        str(service_account),
        image_collection=image_collection,
        storage_bucket=storage_cfg.get("bucket_name") or storage_cfg.get("bucket"),
        vector_search_enabled=False,
        vector_field=vector_field,
    )

    result = db.backfill_embedding_vectors(
        args.user_id,
        limit=args.limit,
        dry_run=not args.yes,
        force=args.force,
    )
    print(f"Collection: users/{args.user_id}/{image_collection}")
    print(f"Vector field: {vector_field}")
    print(
        "Summary: "
        f"scanned={result['scanned']} "
        f"updated={result['updated']} "
        f"skipped={result['skipped']} "
        f"missing_embedding={result['missing_embedding']} "
        f"dry_run={bool(result['dry_run'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
