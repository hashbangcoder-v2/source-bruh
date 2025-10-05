from pathlib import Path
from typing import Any, Dict
from omegaconf import OmegaConf


def load_config(explicit_path: str | None = None) -> Dict[str, Any]:
    """
    Load configuration from config.yaml and ensure required directories exist.
    
    This function:
    1. Loads YAML config using OmegaConf
    2. Resolves any variable interpolation
    3. Creates required directories for storage, database, and tokens
    
    Args:
        explicit_path: Path to config file (optional, defaults to ./config.yaml)
        
    Returns:
        Configuration dictionary with all settings
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        OmegaConf errors: If YAML is malformed
    """
    cfg_path = Path(explicit_path) if explicit_path else Path.cwd() / "config.yaml"
    cfg = OmegaConf.to_container(OmegaConf.load(cfg_path), resolve=True)  # type: ignore[arg-type]

    # Ensure required directories exist
    storage = cfg.get("storage", {})
    Path(storage.get("images_dir", "data/images")).mkdir(parents=True, exist_ok=True)
    Path(storage.get("thumbs_dir", "data/thumbs")).mkdir(parents=True, exist_ok=True)
    db_path = Path(cfg.get("db", {}).get("path", "data/vector.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    token_store = Path(cfg.get("google_photos", {}).get("token_store", "data/google_photos_token.json"))
    token_store.parent.mkdir(parents=True, exist_ok=True)
    return cfg  # type: ignore[return-value]


