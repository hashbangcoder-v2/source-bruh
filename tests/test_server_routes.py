import sys
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the functions package is importable when running tests from repo root.
sys.path.append(str(Path(__file__).resolve().parents[1] / "functions"))

import server  # type: ignore  # noqa: E402


@pytest.fixture
def test_client(monkeypatch, tmp_path):
    image_bytes = b"fake-image-bytes"
    thumb_bytes = b"fake-thumb-bytes"
    image_path = tmp_path / "image.jpg"
    thumb_path = tmp_path / "thumb.jpg"
    image_path.write_bytes(image_bytes)
    thumb_path.write_bytes(thumb_bytes)

    class StubFirestoreDB:
        def __init__(self, *args, **kwargs):
            self._image_path = image_path
            self._thumb_path = thumb_path

        def search(self, query_vector, top_k=20, user_id=None):
            return [
                {
                    "image_rowid": "1",
                    "distance": 0.125,
                    "description": "Sample description",
                    "album_title": "Sample Album",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "thumb_path": str(self._thumb_path),
                    "file_path": str(self._image_path),
                }
            ]

        def get_image_blob(self, image_rowid, prefer_thumb=False):
            if str(image_rowid) != "1":
                return None, None
            path = self._thumb_path if prefer_thumb else self._image_path
            return path.read_bytes(), "image/jpeg"

    class StubGeminiClient:
        def __init__(self, *args, **kwargs):
            pass

        def embed_text(self, text):
            return [0.0, 0.0]

    monkeypatch.setattr(server, "FirestoreDB", StubFirestoreDB)
    monkeypatch.setattr(server, "GeminiClient", StubGeminiClient)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""
            db:
              service_account_key_path: ""
              dimension: 4
            llm:
              oracle_model: "fake"
              embedding_model: "fake"
              api_key_env: "FAKE_KEY"
            google_photos:
              client_secret_path: ""
              scopes: []
              redirect_port: 1008
              token_store: "{tmp_path / 'token.json'}"
            storage:
              images_dir: "{tmp_path / 'images'}"
              thumbs_dir: "{tmp_path / 'thumbs'}"
              max_download_size: "w2048-h2048"
            """
        ).strip()
    )

    app = server.create_app(config_path=str(config_path))
    app.dependency_overrides[server.get_current_user] = lambda: {"uid": "user-123"}
    client = TestClient(app)
    return client, image_bytes, thumb_bytes


def test_search_route_returns_results(test_client):
    client, _, _ = test_client
    response = client.get("/search", params={"q": "diagram"}, headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    item = payload[0]
    assert item["image_rowid"] == "1"
    assert item["thumb_url"].endswith("/image/1?thumb=1")
    assert item["distance"] == pytest.approx(0.125)


def test_image_route_returns_binary(test_client):
    client, image_bytes, thumb_bytes = test_client

    response = client.get("/image/1")
    assert response.status_code == 200
    assert response.content == image_bytes
    assert response.headers["content-type"] == "image/jpeg"

    thumb_response = client.get("/image/1", params={"thumb": 1})
    assert thumb_response.status_code == 200
    assert thumb_response.content == thumb_bytes
    assert thumb_response.headers["content-type"] == "image/jpeg"
