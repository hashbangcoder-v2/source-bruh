from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google_auth_oauthlib.flow import Flow
import datetime
import requests

# Replace with your actual credentials
API_KEY = ""
album_name = 'Twitter'

SCOPES = ['https://www.googleapis.com/auth/photoslibrary', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile', 'openid']
flow = InstalledAppFlow.from_client_secrets_file(
    client_secrets_file='client_secret.json',    
    scopes=SCOPES,    
    )
creds = flow.run_local_server(port=1008)


service = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)
user_info_service = build('oauth2', 'v2', credentials=creds)

service.mediaItems().search(body=
                            dict(filters={"contentFilter": {
                                "includedContentCategories": [
                                                "LANDSCAPES",
                                                "LANDMARKS"
                                            ]
                            }
    }
  )).execute()


# content_filter = build("photoslibrary", "v1").models().contentFilter()
# content_filter.addIncludedContentCategories(categories)  # Add desired categories

# Search photos within the album using filters
albums = service.albums().list().execute()
album_id = None
for album in albums.get('albums', []):
    if album['title'].lower() == album_name.lower():
        album_id = album['id']
        print(f'Found album {album_name} with {album['mediaItemsCount']} items')
        break
if not album_id:
    raise ValueError(f"Album {album_name} not found")


# Set your date range
start_date = datetime.datetime(2019, 1, 1)
end_date = datetime.datetime.now()

# Fetch photos from the album
results = service.mediaItems().search(body={
    'albumId': album_id, 'pageSize': 100,
    # 'filters': {
    #     'dateFilter': {
    #         'ranges': [{
    #             'startDate': {'year': start_date.year, 'month': start_date.month, 'day': start_date.day},
    #             'endDate': {'year': end_date.year, 'month': end_date.month, 'day': end_date.day}
    #         }]
    #     }
    # }
}).execute()
items = results.get('mediaItems', [])
for item in items:
    if item['mimeType'].startswith('image/'):
        # Get the high-quality download URL (adjust size as needed)
        img_url = item['baseUrl'] + '=w1024-h768' 
                
        resp = requests.get(img_url)
        if resp.status_code != 200:
            print(f'Bad Response: {resp.reason}')
        img_data = resp.content        
        filename = item['filename']  # Use the original filename
        with open(f'Saved/{filename}', 'wb') as f:
            f.write(img_data)
        
        print(f"Downloaded: {filename}")

# results = service.mediaItems().search(
#     pageSize=100, albumId='Twitter', filters=content_filter
# ).execute()
# photos = results.get('mediaItems', [])


# # Authenticate and build the service object (refer to Google Photos API documentation for details on authentication)
# service = build("photoslibrary", "v1", developerKey=API_KEY)

# # Call the function to search photos
# filtered_photos = search_photos(service, album_title, categories)

# # Now you have a list of photos (filtered_photos) within the specified album matching the categories
# print(f"Found {len(filtered_photos)} photos in album '{album_title}' matching categories: {', '.join(categories)}")

