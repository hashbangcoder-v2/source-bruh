from typing import Dict, Iterable, List, Optional
import os
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json


class GooglePhotosClient:
    def __init__(self, client_secret_path: str, scopes: List[str], redirect_port: int, token_store: str | None = None, oauth_client: dict | None = None) -> None:
        self.client_secret_path = client_secret_path
        self.scopes = scopes
        self.redirect_port = redirect_port
        self.token_store = token_store
        self.oauth_client = oauth_client or {}
        self.service = self._build_service()
        self.user_email: Optional[str] = None

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
            if self.client_secret_path and os.path.exists(self.client_secret_path):
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_path, self.scopes)
            else:
                # Fallback to config-embedded client (for distribution)
                if not self.oauth_client:
                    raise FileNotFoundError("Missing Google OAuth client credentials; set google_photos.client_secret_path or google_photos.oauth_client in config.yaml")
                flow = InstalledAppFlow.from_client_config(self.oauth_client, self.scopes)
            creds = flow.run_local_server(port=self.redirect_port)
            if self.token_store:
                with open(self.token_store, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
        svc = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)
        try:
            oauth2 = build('oauth2', 'v2', credentials=creds)
            info = oauth2.userinfo().get().execute()
            self.user_email = info.get('email')
        except Exception:
            self.user_email = None
        return svc

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

    def iter_media_items_in_album(self, album_id: str, page_size: int = 100):
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
        url = f"{base_url}={max_size}"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content


