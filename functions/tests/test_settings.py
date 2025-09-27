import sys
from pathlib import Path

from fastapi.testclient import TestClient

current_dir = Path(__file__).resolve()
sys.path.insert(0, str(current_dir.parents[1]))
sys.path.insert(0, str(current_dir.parents[2]))


def test_settings_returns_user_info(monkeypatch):
    sample_cfg = {
        "db": {"service_account_key_path": "dummy"},
        "google_photos": {
            "client_secret_path": "client_secret.json",
            "scopes": ["scope1"],
            "redirect_port": 1234,
            "token_store": "token.json",
            "oauth_client": {"web": {"client_id": "abc"}},
        },
        "llm": {
            "api_key_env": "LLM_API_KEY",
            "oracle_model": "oracle",
            "embedding_model": "embedding",
        },
    }

    class DummyFirestoreDB:
        def __init__(self, service_account_path):
            self.service_account_path = service_account_path

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
    sys.modules["config_loader"] = stub_config_loader

    stub_db = types.ModuleType("db")
    stub_db.FirestoreDB = DummyFirestoreDB
    sys.modules["db"] = stub_db

    from functions import server

    monkeypatch.setattr(server, "load_config", lambda _: sample_cfg)
    monkeypatch.setattr(server, "GooglePhotosClient", DummyPhotosClient)

    app = server.create_app()
    app.dependency_overrides[server.get_current_user] = lambda: {"uid": "user123"}

    with TestClient(app) as client:
        response = client.get("/settings")

        assert response.status_code == 200
        assert response.json() == {
            "email": "user@example.com",
            "album_url": "https://example.com/album",
            "gemini_key_set": True,
        }
