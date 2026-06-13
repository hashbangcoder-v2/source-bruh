export const firebaseConfig = {
  apiKey: '<your-firebase-web-api-key>',
  authDomain: '<your-project-id>.firebaseapp.com',
  projectId: '<your-project-id>',
  storageBucket: '<your-project-id>.firebasestorage.app',
  messagingSenderId: '<your-sender-id>',
  appId: '<your-web-app-id>',
  measurementId: '<your-measurement-id>',
};

export const googleOAuthClientId =
  '<your-web-client-id>.apps.googleusercontent.com';

export const googleOAuthScopes = [
  'profile',
  'email',
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile',
  'https://www.googleapis.com/auth/photoslibrary.readonly',
];

export const serverUrls = {
  production: 'https://<region>-<your-project-id>.cloudfunctions.net/api',
  localDefault: 'http://127.0.0.1:5057',
};
