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
import json
from db import FirestoreDB
from omegaconf import DictConfig, OmegaConf


class GooglePhotosClient:
    def __init__(
        self,
        cfg: Optional[DictConfig] = None,
        db: Optional[FirestoreDB] = None,
        *,
        client_secret_path: Optional[str] = None,
        scopes: Optional[Iterable[str]] = None,
        redirect_port: int = 1008,
        token_store: Optional[str] = None,
        oauth_client: Optional[Dict[str, Any]] = None,
    ):
        self.cfg = cfg
        self.db = db

        self.oauth_client: Optional[Any] = None
        self.redirect_port = redirect_port
        resolved_scopes: Iterable[str] | None = scopes
        resolved_token_store = token_store
        resolved_client_secret = client_secret_path

        if cfg is not None:
            self.oauth_client = getattr(cfg, "oauth_client", None)
            if self.oauth_client is None:
                self.oauth_client = oauth_client
            self.redirect_port = int(getattr(cfg, "redirect_port", redirect_port) or redirect_port)
            cfg_scopes = getattr(cfg, "scopes", None)
            if cfg_scopes is not None and scopes is None:
                resolved_scopes = cfg_scopes
            cfg_token_store = getattr(cfg, "token_store", None)
            if cfg_token_store is not None and token_store is None:
                resolved_token_store = cfg_token_store
            cfg_client_secret = getattr(cfg, "client_secret_path", None)
            if cfg_client_secret and client_secret_path is None:
                resolved_client_secret = cfg_client_secret
        else:
            self.oauth_client = oauth_client

        self.scopes = list(resolved_scopes or [])
        self.token_store = os.fspath(resolved_token_store) if resolved_token_store else None
        self.client_secret_path = os.fspath(resolved_client_secret) if resolved_client_secret else None

        self.service: Optional[Any] = None
        self.credentials: Optional[Credentials] = None
        self.user_email: Optional[str] = None
        self.code_verifier: Optional[str] = None

    def _client_config_dict(self) -> Dict[str, Any]:
        if not self.oauth_client:
            raise RuntimeError("OAuth client configuration is required for this operation.")
        client_config: Any = self.oauth_client
        if isinstance(client_config, DictConfig):
            client_config = OmegaConf.to_container(client_config, resolve=True)  # type: ignore[assignment]
        if not isinstance(client_config, dict):
            raise RuntimeError("OAuth client configuration must be a mapping type.")
        return client_config

    def _ensure_service(self):
        if self.service is None:
            self.service = self._build_service()
        return self.service

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
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secret_path, self.scopes
                )
                creds = flow.run_local_server(port=self.redirect_port)
            else:
                # Use PKCE flow for public clients (Chrome extensions)
                client_config = self._client_config_dict()
                client_info = client_config.get("web") or client_config.get("installed")
                if not client_info or not client_info.get("client_id"):
                    raise FileNotFoundError(
                        "Missing Google OAuth client credentials; set google_photos.oauth_client.web.client_id in config.yaml"
                    )
                creds = self._authenticate_with_pkce()
            if self.token_store:
                with open(self.token_store, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
        if not creds:
            raise RuntimeError("Failed to obtain Google Photos credentials.")

        self.credentials = creds
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


