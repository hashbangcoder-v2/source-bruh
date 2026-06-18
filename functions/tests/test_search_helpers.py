import importlib
import sys
import types
from pathlib import Path


current_dir = Path(__file__).resolve()
sys.path.insert(0, str(current_dir.parents[1]))
sys.path.insert(0, str(current_dir.parents[2]))


def _import_server_with_stubs(monkeypatch):
    sample_cfg = {
        "google_photos": {
            "client_secret_path": "client_secret.json",
            "scopes": [],
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
            pass

    class DummyPhotosClient:
        def __init__(self, cfg, db):
            pass

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
    return server


def test_serialize_timestamp_accepts_datetime_like(monkeypatch):
    server = _import_server_with_stubs(monkeypatch)

    class FirestoreTimestamp:
        def isoformat(self):
            return "2026-01-02T03:04:05+00:00"

    assert server._serialize_timestamp(FirestoreTimestamp()) == "2026-01-02T03:04:05+00:00"


def test_rerank_prefers_newer_year_within_same_relevance_band(monkeypatch):
    server = _import_server_with_stubs(monkeypatch)
    rows = [
        {"distance": 0.12, "title": "2024 OECD GDP"},
        {"distance": 0.13, "title": "2026 OECD GDP"},
        {"distance": 0.30, "title": "2027 unrelated"},
    ]

    ranked = server._rerank_search_rows(rows, top_k=3)

    assert ranked[0]["title"] == "2026 OECD GDP"
    assert ranked[1]["title"] == "2024 OECD GDP"
    assert ranked[2]["title"] == "2027 unrelated"
