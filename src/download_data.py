from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_oauthlib.flow import Flow
import datetime
import requests
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("api_key")
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile', 'openid']

def initialize_google_photos_service():
    """Initialize Google Photos API service."""
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json',
        SCOPES
    )
    creds = flow.run_local_server(port=1008)
    return build('photoslibrary', 'v1', credentials=creds, static_discovery=False)

def download_album_photos(service, album_name):
    """Download all photos from a specific album."""
    # Fetch albums
    albums = service.albums().list(pageSize=50).execute().get('albums', [])
    album = next((a for a in albums if a['title'].lower() == album_name.lower()), None)
    if not album:
        raise ValueError(f"Album '{album_name}' not found.")

    album_id = album['id']
    album_dir = os.path.join("Saved", album_name)
    os.makedirs(album_dir, exist_ok=True)

    next_page_token = None
    while True:
        results = service.mediaItems().search(
            body={"albumId": album_id, "pageSize": 100, "pageToken": next_page_token}
        ).execute()

        items = results.get('mediaItems', [])
        for item in items:
            if item['mimeType'].startswith('image/'):
                img_url = f"{item['baseUrl']}=w1024-h768"
                filename = os.path.join(album_dir, item['filename'])
                response = requests.get(img_url)
                if response.status_code == 200:
                    with open(filename, 'wb') as f:
                        f.write(response.content)

        next_page_token = results.get('nextPageToken')
        if not next_page_token:
            break

    return album_dir

class SQLiteManager:
    def __init__(self, db_name="vector_database.db"):
        # Initialize SQLite connection and load sqlite-vec
        self.conn = sqlite3.connect(db_name)
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        # Create vectors table
        self.cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(
                embedding FLOAT[512],
                timestamp TEXT NOT NULL,
                user_email TEXT NOT NULL,
                description TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def add_record(self, embedding, user_email, timestamp):
        """Add a record to the vectors table."""
        self.cursor.execute(
            "INSERT INTO vectors (embedding, timestamp, user_email, description) VALUES (?, ?, ?, ?)",
            (embedding.tolist(), timestamp, user_email, "dummy")
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

def calculate_embedding(image_path):
    """Calculate vector embedding for an image using external API."""
    url = "https://api.example.com/embedding"  # Replace with actual API endpoint
    files = {"file": open(image_path, "rb")}
    response = requests.post(url, files=files)
    response.raise_for_status()
    return response.json()["embedding"]

def process_album(album_dir, sqlite_manager, user_email):
    """Process all images in an album directory."""
    for image_file in os.listdir(album_dir):
        if image_file.lower().endswith(('jpg', 'jpeg', 'png')):
            image_path = os.path.join(album_dir, image_file)
            embedding = calculate_embedding(image_path)
            timestamp = datetime.datetime.now().isoformat()
            sqlite_manager.add_record(embedding, user_email, timestamp)

if __name__ == "__main__":
    album_name = "Twitter"  # Replace with your album name
    user_email = "user@example.com"  # Replace with actual user email

    # Initialize Google Photos API service
    service = initialize_google_photos_service()

    # Download photos from album
    album_dir = download_album_photos(service, album_name)

    # Initialize SQLite manager
    sqlite_manager = SQLiteManager()

    # Process album and store embeddings in the database
    process_album(album_dir, sqlite_manager, user_email)

    # Close SQLite connection
    sqlite_manager.close()
