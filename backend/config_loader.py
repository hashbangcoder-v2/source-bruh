from pathlib import Path
from typing import Any, Dict
from omegaconf import OmegaConf


def load_config(explicit_path: str | None = None) -> Dict[str, Any]:
    cfg_path = Path(explicit_path) if explicit_path else Path.cwd() / "backend" / "config.yaml"
    cfg = OmegaConf.to_container(OmegaConf.load(cfg_path), resolve=True)  # type: ignore[arg-type]

    # ensure directories exist
    storage = cfg.get("storage", {})
    Path(storage.get("images_dir", "data/images")).mkdir(parents=True, exist_ok=True)
    Path(storage.get("thumbs_dir", "data/thumbs")).mkdir(parents=True, exist_ok=True)
    db_path = Path(cfg.get("db", {}).get("path", "data/vector.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    token_store = Path(cfg.get("google_photos", {}).get("token_store", "data/google_photos_token.json"))
    token_store.parent.mkdir(parents=True, exist_ok=True)
    return cfg  # type: ignore[return-value]


