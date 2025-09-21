// src/api.js
import extCfg from "./extension-config.json";

export async function makeAuthenticatedRequest(path, options = {}) {
  const token = localStorage.getItem('firebaseIdToken');
  const url = `${extCfg.serverBaseUrl}${path}`;
  
  const headers = {
    ...options.headers,
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) {
      // Ignore if the error response is not JSON
    }
    throw new Error(`Request failed: ${response.status} ${errorDetail}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
