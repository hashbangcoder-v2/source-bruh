// src/api.js
import extCfg from "./extension-config.json";
import { auth } from "./firebase";

async function readFromChromeStorage(keys) {
  if (typeof chrome === "undefined" || !chrome?.storage?.local) {
    return {};
  }
  return new Promise((resolve) => {
    try {
      chrome.storage.local.get(keys, (items) => resolve(items || {}));
    } catch (error) {
      console.warn("Unable to read chrome.storage", error);
      resolve({});
    }
  });
}

async function resolveServerBaseUrl() {
  const stored = await readFromChromeStorage(["serverBaseUrl"]);
  const fromStorage = typeof stored.serverBaseUrl === "string" ? stored.serverBaseUrl.trim() : "";
  if (fromStorage) {
    return fromStorage.replace(/\/$/, "");
  }
  return extCfg.serverBaseUrl.replace(/\/$/, "");
}

async function resolveFirebaseToken() {
  const currentUser = auth.currentUser;
  if (currentUser) {
    try {
      const token = await currentUser.getIdToken();
      if (token) {
        return token;
      }
    } catch (error) {
      console.warn("Unable to refresh Firebase ID token", error);
    }
  }

  try {
    return localStorage.getItem("firebaseIdToken");
  } catch (storageError) {
    console.warn("Unable to read cached Firebase token", storageError);
    return null;
  }
}

function buildRequestUrl(baseUrl, path) {
  const trimmedBase = (baseUrl || "").replace(/\/$/, "");
  if (!path) {
    return trimmedBase;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${trimmedBase}${normalizedPath}`;
}

export async function getServerBaseUrl() {
  return resolveServerBaseUrl();
}

export async function checkBackendHealth() {
  const baseUrl = await resolveServerBaseUrl();
  const url = buildRequestUrl(baseUrl, "/health");
  try {
    const response = await fetch(url, { method: "GET" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json().catch(() => ({}));
    return { ok: true, baseUrl, payload };
  } catch (error) {
    return { ok: false, baseUrl, error };
  }
}

/**
 * Performs an authenticated fetch request against the extension backend.
 *
 * The helper automatically attaches the Firebase ID token (when present)
 * and normalises the response so callers always receive either parsed JSON
 * or ``null`` for empty bodies. Error responses surface both HTTP status
 * codes and the backend ``detail`` message when available, making it easier
 * for UI components to react to specific failure modes.
 *
 * @param {string} path - Backend relative path (e.g. ``/settings``).
 * @param {RequestInit} [options] - Optional fetch configuration overrides.
 * @returns {Promise<any>} Parsed JSON payload or ``null`` for empty bodies.
 * @throws {Error & {status?: number}} When the backend responds with an
 *   error status code. The thrown error contains a ``status`` property so
 *   callers can branch on specific response codes (e.g. ``404``).
 */
export async function makeAuthenticatedRequest(path, options = {}) {
  const token = await resolveFirebaseToken();
  const baseUrl = await resolveServerBaseUrl();
  const url = buildRequestUrl(baseUrl, path);

  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const errorText = await response.text();
    let errorDetail = response.statusText;
    try {
      const parsed = errorText ? JSON.parse(errorText) : {};
      errorDetail = parsed.detail || errorDetail;
    } catch (parseError) {
      if (errorText) {
        errorDetail = errorText;
      }
    }
    const error = new Error(`Request failed: ${response.status} ${errorDetail}`);
    error.status = response.status;
    error.url = url;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch (error) {
    return text;
  }
}

export async function authenticatedSearch(query, topK = 20) {
  const params = new URLSearchParams({ q: query, top_k: String(topK) });
  return makeAuthenticatedRequest(`/search?${params.toString()}`);
}
