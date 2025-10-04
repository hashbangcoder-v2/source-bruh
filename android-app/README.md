# Source-Bruh Android App

This document provides instructions on how to set up, build, and test the Source-Bruh Android application locally, with a focus on Windows users.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [1. Firebase Configuration](#1-firebase-configuration)
  - [2. API Key Configuration](#2-api-key-configuration)
- [Building and Running on Android Studio (Windows)](#building-and-running-on-android-studio-windows)
- [Building and Running via Command Line (Windows)](#building-and-running-via-command-line-windows)
- [Testing](#testing)
  - [Firebase Integration](#firebase-integration)
  - [Sharesheet Functionality](#sharesheet-functionality)
  - [Local Testing on a Device](#local-testing-on-a-device)

## Prerequisites

Before you begin, ensure you have the following installed and configured:

-   **Android Studio**: The official IDE for Android development. Download it from the [Android Developer website](https://developer.android.com/studio). When installing, make sure to include the Android SDK and command-line tools.
-   **A Firebase Project**: This app requires a Firebase project with Authentication, Firestore, and Functions enabled.
-   **An Android Device or Emulator**:
    *   **Physical Device**: A physical Android device with USB debugging enabled.
    *   **Emulator**: A configured Android Virtual Device (AVD). You can set this up via **Tools > Device Manager** in Android Studio.

## Setup

### 1. Firebase Configuration

The app uses Firebase for authentication and as its backend.

1.  **Get `google-services.json`**:
    *   Go to your [Firebase Console](https://console.firebase.google.com/).
    *   Select your project.
    *   Navigate to **Project Settings** > **General**.
    *   In the "Your apps" card, select the Android app. If you haven't registered one, click **Add app**, select the Android icon, and follow the on-screen instructions. The package name must be `com.sourcebruh.android`.
    *   Download the `google-services.json` file.
    *   Place this file in the `android-app/app/` directory.

2.  **Enable Google Sign-In**:
    *   In the Firebase Console, go to **Authentication** > **Sign-in method**.
    *   Enable the **Google** provider.
    *   Make sure to provide your SHA-1 certificate fingerprint in the Firebase project settings to authorize your debug builds. To get your SHA-1 fingerprint on Windows:
        *   Open a Command Prompt or PowerShell.
        *   Navigate to the `android-app` directory.
        *   Run the command: `gradlew.bat signingReport`.
        *   Look for the SHA-1 key under the "debug" variant and copy it into your Firebase project settings.

### 2. API Key Configuration

The application requires an API key for its backend services. This can be configured on the **Settings** page within the app itself after logging in.

## Building and Running on Android Studio (Windows)

This is the recommended method for running the app.

1.  **Open the Project**:
    *   Launch Android Studio.
    *   Select **File > Open** and navigate to the `android-app` directory of this project.
    *   Wait for Android Studio to sync the project with Gradle. This may take a few minutes.

2.  **Set up the Run Configuration**:
    *   Near the top-right of the Android Studio window, you'll see a dropdown menu that should say **app**. This is the default run configuration, and you typically don't need to change it.
    *   To the left of this is the device dropdown. You can select a connected physical device or a running emulator.
    *   If you don't have an emulator, you can create one by going to **Tools > Device Manager** and clicking **Create device**.

3.  **Run the App**:
    *   Click the green **Run** button (a triangle icon) next to the device dropdown.
    *   Android Studio will build the app and install it on your selected device/emulator. The app will launch automatically. You can see the build progress in the "Build" window at the bottom of Android Studio.

## Building and Running via Command Line (Windows)

You can also build and run the app manually using the command line.

1.  **Build the APK**:
    *   Open a Command Prompt or PowerShell.
    *   Navigate to the `android-app` directory.
    *   Run the following command to generate a debug APK. The `gradlew.bat` file is the Windows batch script for executing Gradle tasks.

    ```cmd
    gradlew.bat assembleDebug
    ```
    *   The generated APK will be located at `android-app/app/build/outputs/apk/debug/app-debug.apk`.

2.  **Install the APK**:
    *   Use the Android Debug Bridge (ADB) to install the app on your connected device or running emulator. ADB is located in the `platform-tools` directory of your Android SDK.
    *   Make sure your device is listed by running `adb devices`.
    *   Run the install command:
    ```cmd
    adb install app/build/outputs/apk/debug/app-debug.apk
    ```

## Testing

### Firebase Integration

-   **Authentication**: After launching the app, use the Google Sign-In button. You should be prompted to select a Google account and grant permissions. Upon successful login, you will be navigated to the Query page.
-   **Firestore**: Verify that user information is correctly saved and displayed on the Settings page.

### Sharesheet Functionality

1.  Open a gallery app or any app that allows sharing images.
2.  Select an image and tap the "Share" icon.
3.  "Source-Bruh" should appear as an option in the Android sharesheet.
4.  Selecting it should launch the app and handle the image indexing logic.
