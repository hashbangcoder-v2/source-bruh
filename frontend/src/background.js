import extCfg from "./extension-config.json";

/**
 * Identifier for the extension context-menu entry that lets users index
 * images directly from any web page via "Source-Me-Bruh".
 */
const MENU_ID = "source-me-bruh";

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
  chrome.contextMenus.create({
    id: MENU_ID,
    title: "Source-Me-Bruh",
    contexts: ["image"],
  });
  await setInStorage({ serverBaseUrl: extCfg.serverBaseUrl });
});

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
