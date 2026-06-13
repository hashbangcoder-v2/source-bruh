import auth, {FirebaseAuthTypes} from '@react-native-firebase/auth';
import {GoogleSignin} from '@react-native-google-signin/google-signin';
import {googleOAuthClientId, googleOAuthScopes} from '../config';

let configured = false;

export function configureGoogleSignIn() {
  if (configured) {
    return;
  }

  GoogleSignin.configure({
    webClientId: googleOAuthClientId,
    scopes: googleOAuthScopes,
    offlineAccess: false,
  });
  configured = true;
}

export function onAuthChanged(
  listener: (user: FirebaseAuthTypes.User | null) => void,
) {
  configureGoogleSignIn();
  return auth().onAuthStateChanged(listener);
}

export async function signInWithGoogle() {
  configureGoogleSignIn();
  await GoogleSignin.hasPlayServices({showPlayServicesUpdateDialog: true});
  const result = await GoogleSignin.signIn();
  const idToken = result.idToken;

  if (!idToken) {
    throw new Error('Google sign-in did not return an ID token.');
  }

  const credential = auth.GoogleAuthProvider.credential(idToken);
  return auth().signInWithCredential(credential);
}

export async function signOut() {
  await auth().signOut();
  try {
    await GoogleSignin.signOut();
  } catch {
    // Google may not have an active local session after Firebase restores auth.
  }
}

export async function getIdToken() {
  const user = auth().currentUser;
  return user ? user.getIdToken() : null;
}
