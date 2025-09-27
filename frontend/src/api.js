// src/api.js
import extCfg from "./extension-config.json";

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
  const token = localStorage.getItem("firebaseIdToken");
  const url = `${extCfg.serverBaseUrl}${path}`;

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
