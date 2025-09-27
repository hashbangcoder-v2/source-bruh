# Source Bruh? Chrome Extension

Source Bruh? is a Chrome extension backed by Firebase Functions and Firestore that helps you search, index and describe personal image libraries. The popup experience now exposes four dedicated areas—Home, Query, Results and Settings—while the background script offers a "Source-Me-Bruh" context menu for quickly ingesting images from anywhere on the web.

## Features

- **Home (Landing) page** that introduces the extension and gates access to the search experience.
- **Query page** where you can describe the visual you are looking for and trigger semantic search over stored image embeddings.
- **Results grid** that previews the thumbnails returned by the backend.
- **Settings page** with Google sign-in, Google Photos album source configuration, and Gemini API key management.
- **Right-click "Source-Me-Bruh" context menu** that sends any image to the backend for indexing, description generation and vector storage.
- **Firebase-backed auth and storage** with Firestore collections for user profiles, settings, secrets and image metadata.

## Repository layout

```
source-bruh/
├── frontend/               # Vite + React extension source
│   ├── src/
│   │   ├── ExtensionPopup.jsx
│   │   ├── pages/          # Landing, Query, Results, Settings views
│   │   ├── background.js   # Context menu + ingest bridge
│   │   └── offscreen.js    # Google login hosted in an offscreen document
│   └── public/manifest.json
├── functions/              # Firebase Functions (FastAPI) backend code
│   ├── server.py
│   ├── db.py
│   └── ...
├── data/                   # Local image/thumb storage for dev ingest
└── README.md               # This file
```

## Prerequisites

- Node.js 18+
- Python 3.11+ for the Firebase Function / FastAPI server
- Firebase project with:
  - Web app configured for Chrome extension usage (auth domain whitelisted)
  - Service account key for Firestore access
  - Firestore database enabled
- Gemini API access (the key is stored securely in Firestore)

## Backend setup

1. Copy `functions/config.example.yaml` (if present) to `functions/config.yaml` and update Firebase project IDs, storage paths and Gemini models.
2. Place your Firebase service account JSON key referenced by the config.
3. Install backend dependencies:
   ```bash
   cd functions
   pip install -r requirements.txt
   ```
4. Run the FastAPI server locally:
   ```bash
   uvicorn server:app --reload --port 5057
   ```
   The extension points to the deployed Cloud Functions URL by default (`extension-config.json`). For local work, update that file to `http://127.0.0.1:5057` and reload the extension.
5. Firestore layout:
   - `users/{uid}/settings` – stores `album_url`, feature flags and timestamps.
   - `users/{uid}/secrets/gemini_api_key` – securely stores the Gemini API key (never exposed to the client).
   - `users/{uid}/images/{mediaId}` – contains image metadata, timestamps, embeddings, thumbnails and descriptive text.
   - `users/{uid}/google_photos_credentials` – persisted OAuth credentials including refresh tokens for Google Photos ingestion.

## Frontend (extension) setup

1. Install dependencies and build the extension bundle:
   ```bash
   cd frontend
   npm install
   npm run build
   ```
2. In Chrome, open `chrome://extensions`, enable **Developer mode**, click **Load unpacked** and select `frontend/dist`.
3. Click the extension icon to open the popup.

## Using the Settings page

1. Open the popup and click the gear icon to reach **Settings**.
2. **Log in** with Google. The offscreen document hosts the Firebase sign-in flow while respecting extension CSP rules. Successful sign-in persists the refresh token and ID token via Firebase Auth.
3. **Sources** accepts a Google Photos album URL. The extension normalises the URL path before storing it in Firestore and the backend config, ensuring subsequent ingestion jobs know where to fetch media.
4. **API key** expects your Gemini API key. The backend stores it in `users/{uid}/secrets/gemini_api_key`, marks the key as present in settings, resets the in-memory Gemini client, and never echoes the key back to the client.
5. Status messages appear below the form for both success and failure scenarios.

The back arrow always returns you to the Home screen, regardless of whether you entered Settings from Home or Query.

## Querying and results

- From Home, press **Get Started**. If you are authenticated and both the album source and API key are configured, you will land on the Query view.
- Type a natural-language description (e.g. “stacked bar chart 2019 revenue”) and hit enter. The backend embeds the text with Gemini, computes vector similarity against your stored embeddings, and returns the nearest images. Thumbnails render in the Results grid.
- If configuration is incomplete, the Home page prompts you to finish setup via Settings.

## Context menu ingestion

1. Right-click any image in Chrome and choose **Source-Me-Bruh**.
2. The background script validates that you are signed in (Firebase token in `chrome.storage.local`), POSTs the image URL to `/images/from-url`, and shows a notification for success/failure.
3. The backend downloads the image, generates a thumbnail, calls Gemini for a description and embedding, records the page URL, and stores everything in Firestore with the current timestamp when the original media timestamp is unavailable.

## Testing

- Frontend: `cd frontend && npm run build`
- Backend: `cd functions && pytest` (if tests are present)

## Security notes

- Gemini API keys and Google Photos OAuth credentials are kept in user-specific Firestore documents. The settings endpoint only returns whether a key is present—never the key itself.
- The manifest’s Content Security Policy allows Google auth scripts explicitly while keeping other sources locked down.

## Roadmap: Mobile app companion (React Native)

To add a locally-installed Android/iOS client without publishing to app stores, follow these high-level steps:

1. **Project bootstrap** – Create a new React Native app (`npx react-native init`) or Expo project. Configure TypeScript if desired for stronger typing.
2. **Shared configuration** – Extract reusable config (server base URL, Firebase web config) into a shared package or `.env` file consumed by both the extension and the mobile app.
3. **Firebase integration** – Install `@react-native-firebase/app` and `auth` (or Expo’s Firebase JS SDK) to reproduce the Google sign-in flow. For local installs, enable the appropriate OAuth redirect schemes and register the bundle IDs/package names in Firebase.
4. **Secure storage** – Use `@react-native-async-storage/async-storage` (or a secure storage library) to cache the Firebase ID token/refresh token and reuse it for backend calls.
5. **Networking layer** – Mirror the `makeAuthenticatedRequest` helper so the mobile app can call `/settings`, `/search`, `/images/from-url` and `/settings/gemini-key`. Ensure error handling matches the extension for consistent UX.
6. **Screens** – Recreate the four primary views:
   - Home screen that checks readiness (`/settings`) and routes accordingly.
   - Query screen with a text input and search button.
   - Results screen showing thumbnails (use `FlatList` with `Image` components).
   - Settings screen reusing the same fields (email display, album URL input, API key input) and calling the same endpoints.
7. **Image ingestion** – On mobile, add share-sheet integration so the OS “Share” action can send images/URLs into the app, which then POSTs to `/images/from-url` similar to the Chrome context menu.
8. **Local install** – For Android, generate an APK via `gradlew assembleDebug`; for iOS, use Xcode to build and install on-device. Since distribution is local, sideload builds directly.
9. **Testing & parity** – Reuse backend integration tests, add React Native Jest tests if desired, and manually confirm parity with the extension (login, settings persistence, search, ingest).

Documenting these steps before writing code ensures both clients share architecture decisions and reuse as much logic as possible.

## License

This project is provided as-is under the terms specified by the repository owner.
