from typing import Dict, Iterable, List, Optional
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


class GooglePhotosClient:
    def __init__(self, client_secret_path: str, scopes: List[str], redirect_port: int, token_store: str | None = None, oauth_client: dict | None = None) -> None:
        self.client_secret_path = client_secret_path
        self.scopes = scopes
        self.redirect_port = redirect_port
        self.token_store = token_store
        self.oauth_client = oauth_client or {}
        self.service = self._build_service()
        self.user_email: Optional[str] = None
        self.code_verifier: Optional[str] = None

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge"""
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        return code_verifier, code_challenge

    def _authenticate_with_pkce(self) -> Credentials:
        """Authenticate using OAuth 2.0 PKCE flow"""
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
        
        # Start a simple HTTP server to receive the callback
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading
        import webbrowser
        
        auth_code = None
        
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal auth_code
                if self.path.startswith('/?code='):
                    auth_code = self.path.split('code=')[1].split('&')[0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>')
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Authorization failed</h1></body></html>')
        
        # Start server in a thread
        server = HTTPServer(('localhost', self.redirect_port), CallbackHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Wait for authorization code
        while auth_code is None:
            import time
            time.sleep(0.1)
        
        server.shutdown()
        
        # Exchange authorization code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'client_id': client_id,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier
        }
        
        response = requests.post(token_url, data=token_data)
        token_response = response.json()
        
        if 'error' in token_response:
            raise Exception(f"Token exchange failed: {token_response['error']}")
        
        # Create credentials object
        creds = Credentials(
            token=token_response['access_token'],
            refresh_token=token_response.get('refresh_token'),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            scopes=self.scopes
        )
        
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


