import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

current_dir = Path(__file__).resolve()
sys.path.insert(0, str(current_dir.parents[1]))
sys.path.insert(0, str(current_dir.parents[2]))


def test_settings_returns_user_info(monkeypatch):
    sample_cfg = {
        "google_photos": {
            "client_secret_path": "client_secret.json",
            "scopes": ["scope1"],
            "redirect_port": 1234,
            "token_store": "token.json",
            "oauth_client": {"web": {"client_id": "abc"}},
        },
        "llm": {
            "api_key_env": "LLM_API_KEY",
            "embedding_model": "gemini-embedding-2",
        },
        "db": {"service_account_key_path": "dummy", "dimension": 768, "image_collection": "images_test"},
        "storage": {"bucket_name": "test-bucket"},
    }

    class DummyFirestoreDB:
        def __init__(self, service_account_path, image_collection="images", storage_bucket=None, **kwargs):
            self.service_account_path = service_account_path
            self.image_collection = image_collection
            self.storage_bucket = storage_bucket

        def get_user_settings(self, uid):
            return {"album_url": "https://example.com/album", "gemini_api_key": "secret"}

    class DummyPhotosClient:
        def __init__(self, cfg, db):
            self.cfg = cfg
            self.db = db

        def get_user_info_from_db(self, uid):
            return {"email": "user@example.com"}

        def get_auth_url(self):
            return "https://example.com/auth"

    import types

    stub_config_loader = types.ModuleType("config_loader")
    stub_config_loader.load_config = lambda _=None: sample_cfg
    monkeypatch.setitem(sys.modules, "config_loader", stub_config_loader)

    stub_db = types.ModuleType("db")
    stub_db.FirestoreDB = DummyFirestoreDB
    monkeypatch.setitem(sys.modules, "db", stub_db)
    sys.modules.pop("functions.server", None)
    functions_pkg = sys.modules.get("functions")
    if functions_pkg and hasattr(functions_pkg, "server"):
        monkeypatch.delattr(functions_pkg, "server", raising=False)

    server = importlib.import_module("functions.server")

    monkeypatch.setattr(server, "load_config", lambda _: sample_cfg)
    monkeypatch.setattr(server, "GooglePhotosClient", DummyPhotosClient)

    app = server.create_app()
    app.dependency_overrides[server.get_current_user] = lambda: {"uid": "user123"}

    with TestClient(app) as client:
        response = client.get("/settings")

        assert response.status_code == 200
        assert response.json() == {
            "email": "user@example.com",
            "name": "",
            "album_url": "https://example.com/album",
            "gemini_key_set": True,
        }
