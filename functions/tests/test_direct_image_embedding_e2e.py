import datetime
import hashlib
import mimetypes
import os
import sys
from pathlib import Path

import pytest

current_dir = Path(__file__).resolve()
repo_root = current_dir.parents[2]
sys.path.insert(0, str(current_dir.parents[1]))
sys.path.insert(0, str(repo_root))

from functions.config_loader import load_config
from functions.db import FirestoreDB
from functions.ingest import create_thumbnail
from functions.llm import GeminiClient


RUN_E2E = os.environ.get("SOURCE_BRUH_RUN_GEMINI_E2E") == "1"


@pytest.mark.skipif(not RUN_E2E, reason="set SOURCE_BRUH_RUN_GEMINI_E2E=1 to run Gemini/Firestore E2E")
def test_direct_image_embedding_indexes_and_searches_data_test():
    config_path = repo_root / "functions" / "config.yaml"
    cfg = load_config(str(config_path))
    db_cfg = cfg.get("db", {})
    llm_cfg = cfg.get("llm", {})
    storage_cfg = cfg.get("storage", {})

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    assert api_key, "GEMINI_API_KEY or GOOGLE_API_KEY must be set for E2E"

    service_account = db_cfg.get("service_account_key_path")
    service_account_path = Path(service_account or "")
    if service_account_path and not service_account_path.is_absolute():
        service_account_path = config_path.parent / service_account_path
    assert service_account and service_account_path.exists(), (
        "Firestore service account JSON must exist for E2E"
    )

    image_dir = repo_root / "data" / "test"
    image_paths = sorted(path for path in image_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"})
    assert image_paths, "data/test must contain test images"

    user_id = os.environ.get("SOURCE_BRUH_E2E_USER_ID", "e2e-direct-image-embedding")
    image_collection = os.environ.get("SOURCE_BRUH_IMAGE_COLLECTION", "images_test")
    storage_bucket = (
        os.environ.get("SOURCE_BRUH_STORAGE_BUCKET")
        or storage_cfg.get("test_bucket_name")
        or ""
    )
    query = os.environ.get("SOURCE_BRUH_E2E_QUERY", "GST collections India")
    expected_filename = os.environ.get("SOURCE_BRUH_E2E_EXPECTED", "20210129_161245.jpg")

    assert storage_bucket, "SOURCE_BRUH_STORAGE_BUCKET or storage.bucket_name must be set for E2E"

    db = FirestoreDB(
        str(service_account_path),
        image_collection=image_collection,
        storage_bucket=storage_bucket,
    )
    gemini = GeminiClient(
        api_key=api_key,
        embedding_model=llm_cfg.get("embedding_model", "gemini-embedding-2"),
        output_dimensionality=int(db_cfg.get("dimension", 768)),
    )

    run_id = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for image_path in image_paths:
        image_bytes = image_path.read_bytes()
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        embedding = gemini.embed_image(image_bytes, mime_type)
        media_id = f"e2e-{image_path.stem}"
        sha = hashlib.sha256(image_bytes).hexdigest()
        thumb_bytes = create_thumbnail(image_bytes)
        storage_refs = db.store_image_blobs(
            user_id,
            media_id,
            image_bytes,
            thumb_bytes,
            mime_type,
        )

        db.upsert_media_item(
            user_id,
            media_id,
            {
                "image_id": media_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "timestamp_iso": run_id,
                "created_at": run_id,
                "updated_at": run_id,
                "sha256": sha,
                "description": "",
                "embedding": embedding,
                "embedding_kind": "image",
                "embedding_model": llm_cfg.get("embedding_model", "gemini-embedding-2"),
                "embedding_dim": len(embedding),
                "mime_type": mime_type,
                "filename": image_path.name,
                "source_url": image_path.as_posix(),
                **storage_refs,
                "manual_entry": True,
                "source_type": "e2e-fixture",
                "e2e_run_id": run_id,
            },
        )

    query_vector = gemini.embed_query(query)
    results = db.search(query_vector, top_k=5, user_id=user_id)
    ranked_filenames = [row.get("filename") for row in results]

    print(f"E2E collection: users/{user_id}/{image_collection}")
    print(f"E2E query: {query}")
    print(f"E2E ranked filenames: {ranked_filenames}")

    assert ranked_filenames, "search should return at least one indexed image"
    assert expected_filename in ranked_filenames, (
        f"expected {expected_filename} in top 5, got {ranked_filenames}"
    )
