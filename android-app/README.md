# Source-Bruh Android App

This document provides instructions on how to set up, build, and test the Source-Bruh Android application locally.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [1. Firebase Configuration](#1-firebase-configuration)
  - [2. API Key Configuration](#2-api-key-configuration)
- [Building and Running](#building-and-running)
  - [Using Android Studio](#using-android-studio)
  - [Using Gradle and ADB](#using-gradle-and-adb)
- [Testing](#testing)
  - [Firebase Integration](#firebase-integration)
  - [Sharesheet Functionality](#sharesheet-functionality)
  - [Local Testing on a Device](#local-testing-on-a-device)

## Prerequisites

Before you begin, ensure you have the following installed and configured:

-   **Android Studio**: The official IDE for Android development. Download it from the [Android Developer website](https://developer.android.com/studio).
-   **Android SDK**: Make sure you have a recent version of the Android SDK installed through Android Studio's SDK Manager.
-   **A Firebase Project**: This app requires a Firebase project with Authentication, Firestore, and Functions enabled.
-   **An Android Device or Emulator**: A physical Android device or a configured Android Virtual Device (AVD) for running the app.

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
    *   Make sure to provide your SHA-1 certificate fingerprint in the Firebase project settings to authorize your debug builds. You can get it by running `./gradlew signingReport` in the `android-app` directory.

### 2. API Key Configuration

The application requires an API key for its backend services. This can be configured on the **Settings** page within the app itself after logging in.

## Building and Running

You can build and run the app either through Android Studio or via the command line.

### Using Android Studio

1.  Open Android Studio.
2.  Select **File > Open** and navigate to the `android-app` directory of this project.
3.  Let Android Studio sync the project with Gradle.
4.  Select a run configuration (a device or emulator).
5.  Click the **Run** button (green play icon).

### Using Gradle and ADB

1.  **Build the APK**:
    Navigate to the `android-app` directory in your terminal and run the following command to generate a debug APK:
    ```bash
    ./gradlew assembleDebug
    ```
    The generated APK will be located at `android-app/app/build/outputs/apk/debug/app-debug.apk`.

2.  **Install the APK**:
    Use the Android Debug Bridge (ADB) to install the app on your connected device or running emulator:
    ```bash
    adb install app/build/outputs/apk/debug/app-debug.apk
    ```

## Testing

### Firebase Integration

-   **Authentication**: After launching the app, use the "Login With Google" button. You should be prompted to select a Google account and grant permissions. Upon successful login, you should be navigated to the Query page.
-   **Firestore**: Verify that user information is correctly saved and displayed in the Settings page. If you've configured sources, ensure they are correctly persisted.

### Sharesheet Functionality

To test the ability to add new images to be indexed:

1.  Open a gallery app or any app that allows sharing images.
2.  Select an image and tap the "Share" icon.
3.  "Source-Bruh" should appear as an option in the Android sharesheet.
4.  Selecting it should launch the app and handle the image indexing logic.

### Local Testing on a Device

For more advanced Firebase-related testing, you might need to enable a developer mode on your device. For instance, testing features like App Distribution's in-app feedback locally requires this.

1.  **Enable Dev Mode**:
    To enable developer mode for certain Firebase features, run the following ADB command:
    ```shell
    adb shell setprop debug.firebase.appdistro.devmode true
    ```
    While this property is specific to App Distribution, similar flags might be available for other Firebase products.

2.  **Test the Feature**:
    Build and install a debug variant of your app and test the specific Firebase integration you are working on.

3.  **Disable Dev Mode**:
    After testing, you can disable the mode:
    ```shell
    adb shell setprop debug.firebase.appdistro.devmode false
    ```
