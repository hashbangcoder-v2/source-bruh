# Source Bruh Mobile

React Native Android client for local Pixel testing. This is the only active
Android implementation in the repo.

## What Is Implemented

- Google sign-in with Firebase Auth.
- Settings screen for user email, Google Photos source, Gemini API key, and
  local/production backend switching.
- Query screen with semantic search against the existing Firebase Functions API.
- Three-column image results with loading placeholders, timeout fallback, and
  full-screen metadata preview.
- Android sharesheet support for `image/*` and `text/plain`.
- Direct image uploads through `/images/upload` and shared URL ingestion through
  `/images/resolve-url` plus `/images/commit-preview`.

## First-Time Setup

1. Install dependencies:

   ```powershell
   cd react-native
   npm.cmd install
   ```

2. Add Firebase Android config:

   - In Firebase Console, add an Android app with package name
     `com.sourcebruh.mobile`.
   - Download `google-services.json`.
   - Place it at `react-native/android/app/google-services.json`.
   - Add the debug SHA-1 from:

     ```powershell
     cd react-native/android
     .\gradlew.bat signingReport
     ```

3. Start the backend for local phone testing:

   ```powershell
   cd C:\Users\vigne\projects\source-bruh\functions
   $env:LOG_LEVEL="DEBUG"
   $env:PYTHONIOENCODING="utf-8"
   .\venv\Scripts\python.exe -m uvicorn server:app --reload --host 0.0.0.0 --port 5057
   ```

4. Make the Android SDK tools available in each terminal that runs `adb` or
   React Native:

   ```powershell
   $env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
   $env:ANDROID_SDK_ROOT=$env:ANDROID_HOME
   $env:Path="$env:ANDROID_HOME\platform-tools;$env:ANDROID_HOME\emulator;$env:Path"
   ```

5. Choose how the phone reaches the local backend.

   USB reverse proxy, preferred while the Pixel is connected:

   ```powershell
   adb reverse tcp:5057 tcp:5057
   ```

   Then use `http://127.0.0.1:5057` in the app's Local server URL.

   LAN mode, useful without USB:

   ```powershell
   ipconfig
   ```

   Use your Windows LAN IP in the app, for example
   `http://192.168.1.20:5057`, and allow port `5057` through Windows Firewall.

## Run On Pixel 9 Pro

1. Enable Developer options and USB debugging on the phone.
2. Connect by USB and accept the debugging prompt.
3. Verify ADB sees the device:

   ```powershell
   adb devices
   ```

4. Start Metro:

   ```powershell
   cd react-native
   npm.cmd run start
   ```

5. In another terminal, install and launch:

   ```powershell
   cd react-native
   npm.cmd run android
   ```

`npm.cmd run android` first removes the retired native Android package
`com.sourcebruh.android` from any connected device, then installs the current
React Native package `com.sourcebruh.mobile`.

The debug APK is produced at
`react-native/android/app/build/outputs/apk/debug/app-debug.apk`.

## Live Test Checklist

After `npm.cmd run android` prints a line like:

```text
Starting: Intent { ... cmp=com.sourcebruh.mobile/.MainActivity }
```

the native app has been installed and launched on the Pixel. Continue testing on
the phone.

1. Verify the backend is still running in the `functions` terminal.
2. If using USB backend access, confirm the reverse proxy is active:

   ```powershell
   adb reverse --list
   ```

   Expected entry: `tcp:5057 tcp:5057`.

3. Open Source Bruh on the Pixel.
4. Tap the settings button on the login screen.
5. Enable Local server.
6. Set the URL:
   - USB reverse proxy: `http://127.0.0.1:5057`
   - LAN: `http://<your-windows-lan-ip>:5057`
7. Tap Save URL.
8. Tap Test.

Expected result: `Server is reachable.` The backend terminal should log a
`GET /health` request and return `{"ok": true}`.

9. Go back and tap Login With Google.

Expected result: Firebase Auth signs in and the app moves to the query screen.
If login fails, check that Firebase Auth has Google enabled and that the
Firebase Android app for `com.sourcebruh.mobile` has the debug SHA-1 from
`.\gradlew.bat signingReport`.

10. Open Settings again and save a Gemini API key if it is not already set.
11. Enter a Google Photos source path or share URL if you are testing album
    source settings.
12. Run a query such as `growth OECD post-2020`.

Expected result: if images have already been indexed for the signed-in user, the
app shows a three-column result grid. Tapping a tile opens metadata and a larger
preview. If no data exists yet, `No relevant images found for that query.` is
expected.

## Sharesheet Test

1. Open Photos, Files, X, or another app with an image or image post URL.
2. Tap Share.
3. Pick Source Bruh.
4. URL/text shares are sent to `/images/resolve-url`; the backend downloads
   direct image links or the page's social preview image when available.
5. Source Bruh opens the Review Share screen.
6. Verify the preview is the image you meant to save.
7. Optionally add a note. This note is included in the text that gets embedded
   for search.
8. Tap Submit to index.
9. Search for something related to the shared image.

Expected result: URL shares first show `Backend retrieved the image. Review
before indexing.` and the backend terminal logs `POST /images/resolve-url`.
After Submit, `Shared image indexed.` appears and the backend logs
`POST /images/commit-preview`. Raw image-file shares preview locally first and
then log `POST /images/upload` after Submit.

X commonly shares a `text/plain` post URL instead of raw image bytes. In that
case Source Bruh sends the shared URL to `/images/resolve-url`; the backend
fetches the page and prepares the `og:image` or Twitter preview image if the
page exposes one. If the backend cannot retrieve a downloadable image, the app
shows the error and does not index anything. If X omits a downloadable preview
image, share the saved image file from Photos/Files instead.

## What Should Work Now

- Installing and launching the debug app on a USB-connected Pixel.
- Metro Fast Refresh for JavaScript and TypeScript edits while `npm.cmd run
  start` is running.
- Firebase Google sign-in.
- Switching between production and local backend URLs in Settings.
- `/health` connectivity test from the phone.
- Saving Google Photos source settings.
- Saving the per-user Gemini API key.
- Authenticated semantic search through `/search`.
- Displaying thumbnail results and result metadata.
- Sharing `image/*` into the app and uploading it to `/images/upload`.
- Sharing text/page URLs into the app and indexing the page preview image when
  the page exposes one.

## What Is Not Expected To Work Yet

- A physical Pixel cannot reach your PC through `127.0.0.1` unless `adb reverse
  tcp:5057 tcp:5057` is active.
- Native Android changes, Gradle changes, manifest changes, icon changes, or
  dependency changes are not picked up by Fast Refresh. Re-run
  `npm.cmd run android`.
- If Android still opens an old-looking Source Bruh screen, remove the retired
  native package from the Pixel:

  ```powershell
  adb uninstall com.sourcebruh.android
  ```

- Search will not return results until the signed-in user has indexed images.
- Search and upload require a reachable backend, a valid Firebase ID token, and
  a Gemini API key available either in user settings or backend configuration.
- Google Photos ingestion is backend-driven; the mobile app currently stores the
  source setting but does not run a full album sync job by itself.
- Some apps, including X, may share only a post URL rather than the raw image.
  SourceBruh can index it only if the shared page exposes a downloadable preview
  image.

## Runtime Logs

- Local backend logs appear in the PowerShell terminal running `uvicorn`.
  If nothing appears there, the phone is not calling the local backend.
- React Native JavaScript logs appear in the Metro terminal started by
  `npm.cmd run start`. API calls log the method, URL, and HTTP status.
- Android native/device logs are available through:

  ```powershell
  adb logcat
  ```

  To confirm X is handing Source Bruh a URL share, look for an intent like
  `act=android.intent.action.SEND typ=text/plain cmp=com.sourcebruh.mobile/.MainActivity`.

- Deployed Firebase Function logs are separate from local uvicorn logs:

  ```powershell
  firebase.cmd functions:log --project source-bruh
  ```

  A 500 with no local uvicorn log usually means the app is using the deployed
  production URL instead of `http://127.0.0.1:5057` through `adb reverse`.

## Common Issues

- `google-services.json is missing`: place the Firebase Android config at
  `react-native/android/app/google-services.json`.
- `No matching client found for package name 'com.sourcebruh.mobile'`: download
  a Firebase Android config that includes package `com.sourcebruh.mobile`.
- Google login fails: ensure Firebase Auth has Google enabled and the Android
  app has the debug SHA-1 registered.
- Local backend unreachable from the Pixel: run uvicorn with `--host 0.0.0.0`,
  then use either `adb reverse tcp:5057 tcp:5057` with `http://127.0.0.1:5057`
  or use your PC LAN IP and allow port `5057` through Windows Firewall.
- `adb` is not recognized: add
  `C:\Users\vigne\AppData\Local\Android\Sdk\platform-tools` to `Path`, or run
  the Android SDK environment commands above in the current terminal.
- `adb devices` shows `unauthorized`: unlock the Pixel, accept the USB debugging
  prompt, or revoke USB debugging authorizations in Developer options and
  reconnect.
- Build cannot find Android SDK: set `ANDROID_HOME` or create
  `react-native/android/local.properties` with
  `sdk.dir=C\:\\Users\\vigne\\AppData\\Local\\Android\\Sdk`.
