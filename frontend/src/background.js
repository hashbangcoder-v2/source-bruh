import extCfg from "./extension-config.json";

const DEFAULT_GOOGLE_SCOPES = [
  "openid",
  "https://www.googleapis.com/auth/userinfo.email",
  "https://www.googleapis.com/auth/userinfo.profile",
];

function getConfiguredScopes() {
  const scopes = extCfg.googleOAuthScopes;
  if (Array.isArray(scopes) && scopes.length > 0) {
    return scopes;
  }
  return DEFAULT_GOOGLE_SCOPES;
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

async function runChromeIdentityOAuth() {
  if (!chrome.identity?.launchWebAuthFlow) {
    throw new Error("Chrome identity API is unavailable.");
  }

  const rawClientId = extCfg.googleOAuthClientId;
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
  return parseOAuthResponse(redirectUrl, state);
}

/**
 * Identifier for the extension context-menu entry that lets users index
 * images directly from any web page via "Source-Me-Bruh".
 */
const MENU_ID = "source-me-bruh";

/**
 * Ensures the context menu entry exists. Chrome MV3 service workers can be
 * torn down at any time, so we defensively recreate the menu both when the
 * extension is installed/updated and when the worker wakes up again.
 */
function ensureContextMenu() {
  if (!chrome.contextMenus?.create) {
    return;
  }

  chrome.contextMenus.remove(MENU_ID, () => {
    // Ignore "Cannot find menu item" errors when the menu does not exist yet.
    // Accessing lastError consumes the error so it does not surface in logs.
    if (chrome.runtime.lastError) {
      // no-op
    }

    chrome.contextMenus.create({
      id: MENU_ID,
      title: "Source-Me-Bruh",
      contexts: ["image"],
    });
  });
}

const getFromStorage = (keys) =>
  new Promise((resolve) => {
    const storage = chrome.storage?.local;
    if (!storage) {
      resolve({});
      return;
    }
    storage.get(keys, (result) => resolve(result || {}));
  });

const setInStorage = (items) =>
  new Promise((resolve) => {
    const storage = chrome.storage?.local;
    if (!storage) {
      resolve();
      return;
    }
    storage.set(items, () => resolve());
  });

/**
 * Sends a notification (or console log fallback) to inform the user about
 * ingestion success/failure.
 */
const showNotification = (message, isError = false) => {
  if (!chrome.notifications?.create) {
    const logger = isError ? console.error : console.log;
    logger(message);
    return;
  }
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon.png",
    title: "Source Bruh",
    message,
  });
};

chrome.runtime.onInstalled.addListener(async () => {
  ensureContextMenu();
  await setInStorage({ serverBaseUrl: extCfg.serverBaseUrl });
});

chrome.runtime.onStartup?.addListener(() => {
  ensureContextMenu();
});

// MV3 service workers run on-demand. Recreate the menu when this script is
// evaluated so manual reloads also get a context entry without needing to wait
// for an additional event.
ensureContextMenu();

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID || !info.srcUrl) {
    return;
  }
  const stored = await getFromStorage(["firebaseIdToken", "serverBaseUrl"]);
  const token = stored.firebaseIdToken;
  const baseUrl = stored.serverBaseUrl || extCfg.serverBaseUrl;

  if (!token) {
    showNotification("Sign in through the extension before adding images.", true);
    return;
  }

  try {
    await setInStorage({ serverBaseUrl: baseUrl });
    const response = await fetch(`${baseUrl}/images/from-url`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        image_url: info.srcUrl,
        page_url: info.pageUrl || tab?.url || null,
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }

    showNotification("Image added to Source Bruh.");
  } catch (error) {
    showNotification(`Failed to add image: ${error.message}`, true);
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "google-oauth-request") {
    return undefined;
  }

  (async () => {
    try {
      const tokens = await runChromeIdentityOAuth();
      sendResponse({ success: true, payload: tokens });
    } catch (error) {
      sendResponse({ success: false, error: error.message || String(error) });
    }
  })();

  return true;
});
