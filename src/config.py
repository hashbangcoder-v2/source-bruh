import json
import os
from typing import Any, Dict


def load_config(config_path: str = None) -> Dict[str, Any]:
    path = config_path or os.environ.get("SOURCE_BRUH_CONFIG", os.path.join(os.getcwd(), "config.json"))
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Normalize and ensure directories exist
    storage = cfg.get("storage", {})
    images_dir = storage.get("images_dir", "data/images")
    thumbs_dir = storage.get("thumbs_dir", "data/thumbs")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)

    db_path = cfg.get("db", {}).get("path", "data/vector.db")
    db_dir = os.path.dirname(db_path) or "."
    os.makedirs(db_dir, exist_ok=True)

    # Ensure token store dir exists
    token_store = cfg.get("google_photos", {}).get("token_store")
    if token_store:
        os.makedirs(os.path.dirname(token_store), exist_ok=True)

    return cfg


