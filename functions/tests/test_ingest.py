import datetime
import io
import tempfile
import textwrap
import unittest
from pathlib import Path

from PIL import Image

from functions.ingest import create_thumbnail, ingest_once


class StubFirestoreDB:
    def __init__(self) -> None:
        self.saved: dict[str, dict[str, dict]] = {}

    def has_media_item(self, user_id: str, media_id: str) -> bool:
        return media_id in self.saved.get(user_id, {})

    def upsert_media_item(self, user_id: str, media_id: str, image_data: dict) -> str:
        self.saved.setdefault(user_id, {})[media_id] = image_data
        return media_id

    def get_latest_media_timestamp(self, user_id: str, album_title: str | None = None) -> datetime.datetime | None:
        items = self.saved.get(user_id, {})
        best: datetime.datetime | None = None
        for item in items.values():
            if album_title and item.get("album_title") != album_title:
                continue
            ts = item.get("timestamp")
            if isinstance(ts, datetime.datetime):
                if best is None or ts > best:
                    best = ts
        return best


class StubPhotosClient:
    def __init__(self, image_bytes: bytes, *, album_path: str = "album/album-1", media_items: list[dict] | None = None) -> None:
        self.image_bytes = image_bytes
        self.download_calls: list[tuple[str, str]] = []
        self._album = {"id": "album-1", "title": "Test", "productUrl": "https://photos.google.com/album/album-1"}
        self._album_path = album_path
        self._media_items = media_items or [
            {
                "id": "media-1",
                "mimeType": "image/jpeg",
                "baseUrl": "https://example.com/media-1",
                "filename": "image.jpg",
                "mediaMetadata": {
                    "creationTime": "2024-01-01T00:00:00Z",
                    "width": "64",
                    "height": "32",
                },
            }
        ]

    def get_album_by_title(self, title: str):
        if title == self._album["title"]:
            return self._album
        return None

    def get_album_by_path(self, path: str):
        if path.strip("/") == self._album_path.strip("/"):
            return self._album
        return None

    def iter_media_items_in_album(self, album_id: str):
        if album_id != self._album["id"]:
            return
        for item in self._media_items:
            yield item

    def download_image_bytes(self, base_url: str, max_size: str) -> bytes:
        self.download_calls.append((base_url, max_size))
        return self.image_bytes


class StubGeminiClient:
    def describe_image(self, image_bytes: bytes) -> str:
        return "stub description"

    def embed_text(self, text: str):
        return [0.1, 0.2, 0.3]


def _make_test_image() -> bytes:
    img = Image.new("RGB", (16, 16), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class IngestOnceTest(unittest.TestCase):
    def test_ingest_single_media_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            images_dir = tmp_path / "images"
            thumbs_dir = tmp_path / "thumbs"
            config_path = tmp_path / "config.yaml"

            config_text = textwrap.dedent(
                f"""
                server:
                  host: "127.0.0.1"
                  port: 8080

                google_photos:
                  client_secret_path: "{tmp_path / 'client_secret.json'}"
                  scopes:
                    - "https://www.googleapis.com/auth/photoslibrary.readonly"
                  redirect_port: 1008
                  album_paths:
                    - "album/album-1"
                  token_store: "{tmp_path / 'token.json'}"

                llm:
                  oracle_model: "dummy"
                  embedding_model: "dummy-embed"
                  api_key_env: "FAKE_KEY"

                db:
                  service_account_key_path: "{tmp_path / 'service-account.json'}"
                  user_id: "tester"

                storage:
                  images_dir: "{images_dir}"
                  thumbs_dir: "{thumbs_dir}"
                  max_download_size: "w800-h800"
                """
            ).strip()
            config_path.write_text(config_text, encoding="utf-8")

            image_bytes = _make_test_image()

            stub_db = StubFirestoreDB()
            photos_client = StubPhotosClient(image_bytes)
            gemini_client = StubGeminiClient()

            ingest_once(
                config_path=str(config_path),
                db=stub_db,
                photos_client=photos_client,
                gemini_client=gemini_client,
            )

            stored = stub_db.saved["tester"]["media-1"]
            self.assertEqual(stored["album_title"], "Test")
            self.assertEqual(stored["description"], "stub description")
            self.assertEqual(stored["embedding"], [0.1, 0.2, 0.3])
            self.assertEqual(len(stored["sha256"]), 64)
            self.assertEqual(stored["album_path"], "album/album-1")
            self.assertEqual(stored["timestamp_iso"], "2024-01-01T00:00:00Z")
            self.assertIsInstance(stored["timestamp"], datetime.datetime)
            self.assertEqual(stored["image_bytes"], image_bytes)
            self.assertEqual(stored["thumbnail_bytes"], create_thumbnail(image_bytes))
            self.assertTrue((images_dir / "image.jpg").exists())
            self.assertTrue((thumbs_dir / "image.jpg").exists())
            self.assertEqual(len(photos_client.download_calls), 1)

            ingest_once(
                config_path=str(config_path),
                db=stub_db,
                photos_client=photos_client,
                gemini_client=gemini_client,
            )

            self.assertEqual(len(stub_db.saved["tester"]), 1)
            self.assertEqual(len(photos_client.download_calls), 1)

    def test_skips_items_before_latest_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            images_dir = tmp_path / "images"
            thumbs_dir = tmp_path / "thumbs"
            config_path = tmp_path / "config.yaml"

            config_text = textwrap.dedent(
                f"""
                server:
                  host: "127.0.0.1"
                  port: 8080

                google_photos:
                  client_secret_path: "{tmp_path / 'client_secret.json'}"
                  scopes:
                    - "https://www.googleapis.com/auth/photoslibrary.readonly"
                  redirect_port: 1008
                  album_paths:
                    - "album/album-1"
                  token_store: "{tmp_path / 'token.json'}"

                llm:
                  oracle_model: "dummy"
                  embedding_model: "dummy-embed"
                  api_key_env: "FAKE_KEY"

                db:
                  service_account_key_path: "{tmp_path / 'service-account.json'}"
                  user_id: "tester"

                storage:
                  images_dir: "{images_dir}"
                  thumbs_dir: "{thumbs_dir}"
                  max_download_size: "w800-h800"
                """
            ).strip()
            config_path.write_text(config_text, encoding="utf-8")

            image_bytes = _make_test_image()

            stub_db = StubFirestoreDB()
            existing_ts = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
            stub_db.upsert_media_item(
                "tester",
                "existing",
                {
                    "album_title": "Test",
                    "timestamp": existing_ts,
                },
            )

            old_item = {
                "id": "media-older",
                "mimeType": "image/jpeg",
                "baseUrl": "https://example.com/media-older",
                "filename": "older.jpg",
                "mediaMetadata": {
                    "creationTime": "2024-01-01T00:00:00Z",
                    "width": "32",
                    "height": "32",
                },
            }
            photos_client = StubPhotosClient(image_bytes, media_items=[old_item])
            gemini_client = StubGeminiClient()

            ingest_once(
                config_path=str(config_path),
                db=stub_db,
                photos_client=photos_client,
                gemini_client=gemini_client,
            )

            # No new items should be added
            self.assertEqual(len(stub_db.saved["tester"]), 1)
            # Download should never be attempted for the older item
            self.assertEqual(len(photos_client.download_calls), 0)


if __name__ == "__main__":
    unittest.main()
