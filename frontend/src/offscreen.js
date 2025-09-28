import { GoogleAuthProvider, signInWithCredential } from "firebase/auth";
import { auth } from "./firebase";
import extensionConfig from "./extension-config.json";

function getConfiguredScopes() {
  const scopes = extensionConfig.googleOAuthScopes;
  if (Array.isArray(scopes) && scopes.length > 0) {
    return scopes;
  }
  return ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"];
}

function randomString() {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, "0")).join("");
}

function buildGoogleOAuthUrl({ clientId, redirectUri, scopes, state, nonce }) {
  const url = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("response_type", "token id_token");
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", scopes.join(" "));
  url.searchParams.set("state", state);
  url.searchParams.set("nonce", nonce);
  url.searchParams.set("prompt", "select_account");
  url.searchParams.set("include_granted_scopes", "true");
  return url.toString();
}

function launchWebAuthFlow(details) {
  return new Promise((resolve, reject) => {
    try {
      chrome.identity.launchWebAuthFlow(details, (redirectUrl) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(redirectUrl);
      });
    } catch (error) {
      reject(error);
    }
  });
}

function parseOAuthResponse(url, expectedState) {
  if (!url) {
    throw new Error("Google sign-in was cancelled.");
  }

  const fragmentIndex = url.indexOf("#");
  const queryIndex = url.indexOf("?");
  let paramsString = "";

  if (fragmentIndex !== -1) {
    paramsString = url.substring(fragmentIndex + 1);
  } else if (queryIndex !== -1) {
    paramsString = url.substring(queryIndex + 1);
  }

  const params = new URLSearchParams(paramsString);
  const returnedState = params.get("state");

  if (expectedState && returnedState && expectedState !== returnedState) {
    throw new Error("OAuth state mismatch. Please try again.");
  }

  const idToken = params.get("id_token");
  if (!idToken) {
    const errorDescription = params.get("error_description") || params.get("error") || "Missing ID token from Google.";
    throw new Error(errorDescription);
  }

  const accessToken = params.get("access_token") || undefined;
  return { idToken, accessToken };
}

async function signInWithGoogleViaIdentity() {
  if (typeof chrome === "undefined" || !chrome.identity?.launchWebAuthFlow) {
    throw new Error("Chrome identity API is unavailable.");
  }

  const rawClientId = extensionConfig.googleOAuthClientId;
  const clientId = typeof rawClientId === "string" ? rawClientId.trim() : "";
  if (!clientId) {
    throw new Error("Google OAuth client ID is not configured.");
  }

  const redirectUri = chrome.identity.getRedirectURL("oauth2");
  const state = randomString();
  const nonce = randomString();
  const scopes = getConfiguredScopes();

  const authUrl = buildGoogleOAuthUrl({ clientId, redirectUri, scopes, state, nonce });
  const redirectUrl = await launchWebAuthFlow({ url: authUrl, interactive: true });
  const { idToken, accessToken } = parseOAuthResponse(redirectUrl, state);
  const credential = GoogleAuthProvider.credential(idToken, accessToken);
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
