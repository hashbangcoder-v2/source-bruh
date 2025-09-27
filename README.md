# Source Bruh

__Source Bruh__ is a React Native Android app for saving images into a private searchable image index. Share an image or image URL into the app, review it, optionally crop it, add a note, and index it. Search embeds the query with Gemini and uses Firestore vector search to retrieve matching images stored in Cloud Storage.

Next time you wont look silly when you make that ridiculous sounding claim whena arguing with an anon-pfp twitter account and cannot back it up with a source! You know, that one really cool infographic you saw on a 3am doomscroll-sesh from 6 months ago that you cant find now. __Source Bruh__ was born from the pain of many such humiliations and hours of fiddling with Twitter's broken search index

The project is BYOK + BYOB (bring-your-own-backend and bring-your-own-key) use. The repository ships only placeholder Firebase config; each developer or user deploys their own Firebase/GCP backend and supplies their own Gemini API key. You know, because i cant afford to pay for your Gemini API calls and Firestore read/writes and Google isnt a particularly generous company these days.

Currently, the app is Android-only

## Release Changelog

### v0.1.0

- React Native Android app.
- Firebase Auth sign-in.
- Share-sheet image intake.
- Review, crop, and add-to-index flow.
- `gemini-2-embeddings` for image and query embeddings.
- Firestore vector search.
- Cloud Storage image persistence.
- Full-screen result viewer with metadata and copy support.


## Next Up
- Detection logic when hitting rate-limits of Gemini/Firestore free-tier
- Swap out gemini embeddings for a local lighweight model that can run on-device
- Add some more analytics and usage stats , because i like charts and numbers
- Tighten the search-retrieval logic, proper intent detection and query expansion

## (Basic) Features

- Android share-sheet intake for images and image URLs.
- Review screen before indexing, with optional crop and user description.
- Firestore native vector search.
- Cloud Storage image and thumbnail storage.
- Firebase Auth with Google sign-in.
- Profile page with basic account and usage stats.
- Full-screen result viewer with metadata, swipe navigation, and image copy support.

## Architecture

- Android app: React Native app in `react-native/`
- Authentication: Firebase Auth with Google sign-in
- Backend: Firebase Functions v2 hosting the FastAPI app in `functions/server.py`
- Metadata database: Firestore under `users/{uid}/images`
- Vector search: Firestore native vector index on `embedding_vector`
- Image storage: Cloud Storage bucket configured in `functions/config.yaml`
- Secrets: Gemini key stored in Firebase Secret Manager for shared-backend deployment, or supplied by a user for BYOK flows

## Repository Layout

```text
source-bruh/
+-- functions/       # Firebase Functions / FastAPI backend
+-- react-native/    # Android React Native app
+-- scripts/         # helper scripts
+-- firebase.json
+-- README.md
+-- LICENSE
```

## Firebase Setup

Create one Firebase project backed by one Google Cloud project. Replace every placeholder with values from your own project.

1. Enable Firebase Auth and Google sign-in.
2. Create a Firestore database.
3. Add an Android Firebase app with package name `com.sourcebruh.mobile`.
4. Download `google-services.json` to `react-native/android/app/google-services.json`.
5. Create one production Cloud Storage bucket.
6. Create the Firestore vector index.
7. Store a Gemini key in Firebase Secret Manager if you want the backend to provide embeddings without requiring each app user to add their own key.

PowerShell:

```powershell
gcloud.cmd storage buckets create gs://<project-id>-prod-images --project=<project-id> --location=us-central1

gcloud.cmd firestore indexes composite create `
  --collection-group=images `
  --query-scope=COLLECTION `
  --field-config='field-path=embedding_vector,vector-config={dimension=768,flat}' `
  --database="(default)"

firebase.cmd functions:secrets:set GEMINI_API_KEY
firebase.cmd deploy --only functions
```

Linux/macOS:

```bash
gcloud storage buckets create gs://<project-id>-prod-images --project=<project-id> --location=us-central1

gcloud firestore indexes composite create \
  --collection-group=images \
  --query-scope=COLLECTION \
  --field-config='field-path=embedding_vector,vector-config={dimension=768,flat}' \
  --database="(default)"

firebase functions:secrets:set GEMINI_API_KEY
firebase deploy --only functions
```

## Project Configuration

Update these files for your Firebase project:

- `.firebaserc`: set `projects.default` to your Firebase project ID.
- `functions/config.yaml`: set the service account path, production bucket, and optional OAuth values.
- `react-native/src/config.ts`: set Firebase web config, Google OAuth web client ID, and production backend URL.
- `react-native/android/app/google-services.json`: download this from Firebase Console for the Android app.

Do not share service-account JSON, keystores, downloaded Firebase config files, or private API keys.

## Private Backend Overlay

For local work, you can keep private config in an ignored overlay directory and copy it into place before building:

```text
.local/firebase-backend/.firebaserc
.local/firebase-backend/functions.config.yaml
.local/firebase-backend/react-native.config.ts
.local/firebase-backend/google-services.json
```

Optional private files:

```text
.local/firebase-backend/gcloud-service-account.json
.local/firebase-backend/keystore.properties
.local/firebase-backend/source-bruh-release.keystore
```

Apply the overlay.

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\apply-private-backend.ps1
```

Linux/macOS with PowerShell installed:

```bash
pwsh -File ./scripts/apply-private-backend.ps1
```

## Backend Local Run

PowerShell:

```powershell
cd functions
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
$env:LOG_LEVEL="DEBUG"
$env:GOOGLE_API_KEY="<your Gemini key>"
.\venv\Scripts\uvicorn.exe server:app --reload --host 0.0.0.0 --port 5057
```

Linux/macOS:

```bash
cd functions
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export LOG_LEVEL=DEBUG
export GOOGLE_API_KEY="<your Gemini key>"
uvicorn server:app --reload --host 0.0.0.0 --port 5057
```

## Android Local Run

PowerShell:

```powershell
cd react-native
npm.cmd install
npm.cmd run start
npm.cmd run android
```

Linux/macOS:

```bash
cd react-native
npm install
npm run start
npm run android
```

Debug builds use Metro. Release APKs bundle JavaScript and do not need Metro at runtime.

## BYOK Notes

The backend first looks for a user-specific Gemini key saved in Firestore user settings. If no user key is available, it falls back to the shared backend key from Firebase Secret Manager or local environment variables.

For a single-user deployment, the simplest setup is a backend-level `GEMINI_API_KEY`. For a multi-user deployment, prefer BYOK so each user controls their own Gemini usage and quota.


## License

MIT. See `LICENSE`.

## Acknowledgements

Built with generous assistance from Codex.
