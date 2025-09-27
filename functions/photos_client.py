from typing import Any, Dict, List, Optional, Mapping
import os
import requests
import secrets
import hashlib
import base64
import urllib.parse
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import json
from db import FirestoreDB
from omegaconf import DictConfig


class GooglePhotosClient:
    def __init__(self, cfg: DictConfig | Mapping[str, Any], db: FirestoreDB):
        self.cfg = cfg
        self.db = db
        self.oauth_client = self._cfg_value("oauth_client", {})
        self.redirect_port = self._cfg_value("redirect_port")
        scopes = self._cfg_value("scopes", [])
        self.scopes = list(scopes) if scopes is not None else []
        self.token_store = self._cfg_value("token_store")  # Keep for local dev maybe, but not for cloud
        self.client_secret_path = self._cfg_value("client_secret_path")

    def _cfg_value(self, key: str, default: Any | None = None) -> Any:
        if isinstance(self.cfg, Mapping):
            return self.cfg.get(key, default)
        return getattr(self.cfg, key, default)

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        return code_verifier, code_challenge

    def get_auth_url(self) -> str:
        client_id = self.oauth_client["web"]["client_id"]
        redirect_uri = f"http://localhost:{self.redirect_port}/"
        
        # Generate PKCE pair
        code_verifier, code_challenge = self._generate_pkce_pair()
        self.code_verifier = code_verifier
        
        # Build authorization URL
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
            f"response_type=code&"
            f"scope={urllib.parse.quote(' '.join(self.scopes))}&"
            f"code_challenge={code_challenge}&"
            f"code_challenge_method=S256&"
            f"access_type=offline"
        )
        
        print(f"Please visit this URL to authorize the application:")
        print(f"{auth_url}")
        print(f"\nWaiting for authorization code...")
        
        return auth_url

    def get_credentials_from_db(self, uid: str) -> Optional[Credentials]:
        """Gets user's Google Photos API credentials from Firestore."""
        return self.db.get_google_photos_credentials(uid)

    def get_user_info_from_db(self, uid: str) -> dict:
        """Gets user's info from Firestore."""
        return self.db.get_user_info(uid)

    def get_credentials_from_code(self, code: str, uid: str) -> Credentials:
        """
        Handles the OAuth callback, exchanging the authorization code for credentials
        and saving them to Firestore. Also fetches and saves user info.
        """
        client_id = self.oauth_client["web"]["client_id"]
        redirect_uri = f"http://localhost:{self.redirect_port}/"
        
        # Generate PKCE pair
        code_verifier, code_challenge = self._generate_pkce_pair()
        self.code_verifier = code_verifier
        
        # Use a flow object to complete the auth process
        flow = InstalledAppFlow.from_client_config(
            self.oauth_client, self.scopes, redirect_uri=redirect_uri
        )

        # Exchange code for credentials
        flow.fetch_token(code=code, code_verifier=code_verifier)
        creds = flow.credentials

        # Save credentials to Firestore
        self.db.save_google_photos_credentials(uid, creds)

        # Get user info and save to Firestore
        try:
            oauth2 = build("oauth2", "v2", credentials=creds)
            info = oauth2.userinfo().get().execute()
            self.db.save_user_info(uid, info)
        except Exception as e:
            # Log this error but don't fail the whole process
            print(f"Error fetching user info: {e}")

        return creds

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
                creds = flow.run_local_server(port=self.redirect_port)
            else:
                # Use PKCE flow for public clients (Chrome extensions)
                if not self.oauth_client or not self.oauth_client.get("web", {}).get("client_id"):
                    raise FileNotFoundError("Missing Google OAuth client credentials; set google_photos.oauth_client.web.client_id in config.yaml")
                creds = self._authenticate_with_pkce()
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


