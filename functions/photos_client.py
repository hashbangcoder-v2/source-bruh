from typing import Any, Dict, Iterable, List, Optional
import os
import requests
import secrets
import hashlib
import base64
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json

try:  # pragma: no cover
    from .db import FirestoreDB
except ImportError:  # pragma: no cover
    from db import FirestoreDB


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
        client_config = self._client_config_dict()
        client_info = client_config.get("web") or client_config.get("installed")
        if not client_info:
            raise RuntimeError("OAuth client configuration must include a 'web' or 'installed' section.")
        client_id = client_info["client_id"]
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
        if not self.db:
            raise RuntimeError("Firestore database client is not configured.")
        return self.db.get_google_photos_credentials(uid)

    def get_user_info_from_db(self, uid: str) -> dict:
        """Gets user's info from Firestore."""
        if not self.db:
            raise RuntimeError("Firestore database client is not configured.")
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
            self._client_config_dict(), self.scopes, redirect_uri=redirect_uri
        )

        # Exchange code for credentials
        flow.fetch_token(code=code, code_verifier=code_verifier)
        creds = flow.credentials

        if self.db:
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

        creds = self._credentials or self._load_credentials_from_db() or self._load_credentials_from_token_store()
        creds = self._ensure_credentials(creds)
        self._credentials = creds
        self._persist_credentials(creds)
        svc = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)
        try:
            oauth2 = build('oauth2', 'v2', credentials=creds)
            info = oauth2.userinfo().get().execute()
            self.user_email = info.get('email')
        except Exception:
            self.user_email = None
        self.service = svc
        return svc

    def _authenticate_with_pkce(self) -> Credentials:
        client_config = self._client_config_dict()
        redirect_uri = f"http://localhost:{self.redirect_port}/"
        flow = Flow.from_client_config(client_config, scopes=self.scopes, redirect_uri=redirect_uri)

        code_verifier, code_challenge = self._generate_pkce_pair()
        self.code_verifier = code_verifier

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )

        auth_result: Dict[str, Optional[str]] = {"code": None, "error": None}

        class OAuthCallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self_inner):  # type: ignore[override]
                parsed = urllib.parse.urlparse(self_inner.path)
                params = urllib.parse.parse_qs(parsed.query)
                if "code" in params:
                    auth_result["code"] = params["code"][0]
                    message = "Authentication complete. You may close this window."
                    status = 200
                else:
                    auth_result["error"] = params.get("error", ["Unknown error"])[0]
                    message = "Authentication failed. You may close this window."
                    status = 400
                self_inner.send_response(status)
                self_inner.send_header("Content-Type", "text/html; charset=utf-8")
                self_inner.end_headers()
                self_inner.wfile.write(message.encode("utf-8"))

            def log_message(self_inner, format: str, *args: Any) -> None:  # type: ignore[override]
                return

        server = HTTPServer(("localhost", self.redirect_port), OAuthCallbackHandler)
        try:
            print("Please visit this URL to authorize the application:")
            print(auth_url)
            print("\nWaiting for authorization code...")
            server.handle_request()
        finally:
            server.server_close()

        if not auth_result["code"]:
            error = auth_result["error"] or "Authorization code not received."
            raise RuntimeError(f"Failed to obtain authorization code: {error}")

        flow.fetch_token(code=auth_result["code"], code_verifier=code_verifier)
        return flow.credentials

    def list_albums(self, page_size: int = 50) -> List[Dict]:
        albums: List[Dict] = []
        next_token: Optional[str] = None
        service = self._ensure_service()
        while True:
            result = service.albums().list(pageSize=page_size, pageToken=next_token).execute()
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

    def get_album_by_path(self, path: str) -> Optional[Dict]:
        normalized = (path or "").strip().strip('/')
        if not normalized:
            return None
        for album in self.list_albums():
            product_url = album.get('productUrl', '')
            if product_url:
                parsed = urllib.parse.urlparse(product_url)
                product_path = parsed.path.strip('/')
                if product_path and product_path.lower() == normalized.lower():
                    return album
            share_info = album.get('shareInfo') or {}
            share_url = share_info.get('shareableUrl') or ''
            if share_url:
                parsed_share = urllib.parse.urlparse(share_url)
                share_path = parsed_share.path.strip('/')
                if share_path and share_path.lower() == normalized.lower():
                    return album
        return None

    def iter_media_items_in_album(self, album_id: str, page_size: int = 100):
        next_page_token: Optional[str] = None
        service = self._ensure_service()
        while True:
            body = {"albumId": album_id, "pageSize": page_size}
            if next_page_token:
                body["pageToken"] = next_page_token
            result = service.mediaItems().search(body=body).execute()
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


