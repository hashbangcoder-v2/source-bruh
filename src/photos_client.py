from typing import Dict, Iterable, List, Optional
import os
import io
import time

import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json


class GooglePhotosClient:
    def __init__(self, client_secret_path: str, scopes: List[str], redirect_port: int, token_store: str | None = None) -> None:
        self.client_secret_path = client_secret_path
        self.scopes = scopes
        self.redirect_port = redirect_port
        self.token_store = token_store
        self.service = self._build_service()

    def _build_service(self):
        creds = None
        if self.token_store and os.path.exists(self.token_store):
            try:
                with open(self.token_store, "r", encoding="utf-8") as f:
                    data = json.load(f)
                creds = Credentials.from_authorized_user_info(data, scopes=self.scopes)
            except Exception:
                creds = None
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_path, self.scopes)
            creds = flow.run_local_server(port=self.redirect_port)
            if self.token_store:
                with open(self.token_store, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
        return build('photoslibrary', 'v1', credentials=creds, static_discovery=False)

    def list_albums(self, page_size: int = 50) -> List[Dict]:
        albums: List[Dict] = []
        next_token: Optional[str] = None
        while True:
            result = self.service.albums().list(pageSize=page_size, pageToken=next_token).execute()
            albums.extend(result.get('albums', []))
            next_token = result.get('nextPageToken')
            if not next_token:
                break
        return albums

    def get_album_by_title(self, title: str) -> Optional[Dict]:
        for album in self.list_albums():
            if album.get('title', '').lower() == title.lower():
                return album
        return None

    def iter_media_items_in_album(self, album_id: str, page_size: int = 100) -> Iterable[Dict]:
        next_page_token: Optional[str] = None
        while True:
            body = {"albumId": album_id, "pageSize": page_size}
            if next_page_token:
                body["pageToken"] = next_page_token
            result = self.service.mediaItems().search(body=body).execute()
            items = result.get('mediaItems', [])
            for item in items:
                yield item
            next_page_token = result.get('nextPageToken')
            if not next_page_token:
                break

    def download_image_bytes(self, base_url: str, max_size: str) -> bytes:
        # base_url expects size spec appended, e.g., =w2048-h2048
        url = f"{base_url}={max_size}"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content


