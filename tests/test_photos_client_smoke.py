from pathlib import Path
import sys
from typing import Any, Dict, Optional

import pytest

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "functions"))

from functions.photos_client import GooglePhotosClient  # noqa: E402


class _DummyRequest:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def execute(self) -> Dict[str, Any]:
        return self._payload


class _DummyAlbums:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def list(self, pageSize: int = 50, pageToken: Optional[str] = None) -> _DummyRequest:  # noqa: N802 - API parity
        return _DummyRequest(self._payload)


class _DummyMediaItems:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def search(self, body: Dict[str, Any]) -> _DummyRequest:  # noqa: ARG002 - parity with google API
        return _DummyRequest(self._payload)


class _DummyService:
    def __init__(self, albums_payload: Dict[str, Any], media_payload: Dict[str, Any]):
        self._albums_payload = albums_payload
        self._media_payload = media_payload

    def albums(self) -> _DummyAlbums:
        return _DummyAlbums(self._albums_payload)

    def mediaItems(self) -> _DummyMediaItems:  # noqa: N802 - API parity
        return _DummyMediaItems(self._media_payload)


@pytest.fixture()
def dummy_service_payloads() -> Dict[str, Dict[str, Any]]:
    return {
        "albums": {"albums": [{"title": "Sample"}]},
        "media": {"mediaItems": [{"id": "1"}]},
    }


def test_list_albums_smoke(monkeypatch: pytest.MonkeyPatch, dummy_service_payloads: Dict[str, Dict[str, Any]]):
    service = _DummyService(dummy_service_payloads["albums"], dummy_service_payloads["media"])
    build_calls = {"count": 0}

    def _fake_build(self: GooglePhotosClient):
        build_calls["count"] += 1
        self.service = service
        return service

    monkeypatch.setattr(GooglePhotosClient, "_build_service", _fake_build)

    client = GooglePhotosClient(
        client_secret_path=None,
        scopes=["https://www.googleapis.com/auth/photoslibrary.readonly"],
        redirect_port=1234,
        token_store=None,
        oauth_client={
            "web": {
                "client_id": "fake-client",
                "auth_uri": "https://example.com/auth",
                "token_uri": "https://example.com/token",
                "redirect_uris": ["http://localhost:1234/"],
            }
        },
    )

    albums = client.list_albums()
    assert albums == dummy_service_payloads["albums"]["albums"]
    assert client.service is service

    # Verify the cached service avoids repeated builds.
    more_albums = client.list_albums()
    assert more_albums == albums
    assert build_calls["count"] == 1
