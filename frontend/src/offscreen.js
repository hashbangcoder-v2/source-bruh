import { GoogleAuthProvider, signInWithCredential } from "firebase/auth";
import { auth } from "./firebase";

function requestChromeIdentityTokens() {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendMessage({ type: "google-oauth-request" }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!response) {
          reject(new Error("No response from background during OAuth."));
          return;
        }
        if (!response.success) {
          reject(new Error(response.error || "OAuth flow failed."));
          return;
        }
        resolve(response.payload);
      });
    } catch (error) {
      reject(error);
    }
  });
}

async function signInWithGoogleViaIdentity() {
  if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) {
    throw new Error("Chrome messaging API is unavailable.");
  }

  const { idToken, accessToken } = await requestChromeIdentityTokens();
  const credential = GoogleAuthProvider.credential(idToken, accessToken || undefined);
  return signInWithCredential(auth, credential);
}

// Listen for messages from the extension popup
chrome.runtime.onMessage.addListener(async (message) => {
  if (message.type === "firebase-login") {
    try {
      const result = await signInWithGoogleViaIdentity();
      chrome.runtime.sendMessage({ type: "firebase-login-success", payload: result.user });
    } catch (error) {
      chrome.runtime.sendMessage({ type: "firebase-login-failure", payload: error.message });
    }
  }
  return true;
});
