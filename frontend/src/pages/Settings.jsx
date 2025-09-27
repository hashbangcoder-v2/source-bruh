import React, { useState, useEffect } from "react";
import { auth } from "../firebase";
import { signOut, onAuthStateChanged } from "firebase/auth";
import { makeAuthenticatedRequest } from "../api";

/**
 * Path to the offscreen document that hosts the Firebase auth flow.
 */
const OFFSCREEN_DOCUMENT_PATH = "/offscreen.html";

/**
 * Checks whether the extension already has an offscreen document available.
 */
async function hasOffscreenDocument() {
    if (typeof chrome === 'undefined' || !chrome.runtime) {
        return false;
    }
    if ('getContexts' in chrome.runtime) {
        const contexts = await chrome.runtime.getContexts({
            contextTypes: ['OFFSCREEN_DOCUMENT'],
            documentUrls: [chrome.runtime.getURL(OFFSCREEN_DOCUMENT_PATH)]
        });
        return contexts.length > 0;
    } else {
        // Fallback for older browsers
        const views = chrome.extension.getViews({ type: 'OFFSCREEN_DOCUMENT' });
        return views.length > 0;
    }
}

/**
 * Lazily creates the offscreen document that powers Firebase Auth.
 */
async function createOffscreenDocument() {
    if (typeof chrome === 'undefined' || !chrome.offscreen) {
        return;
    }
    if (!await hasOffscreenDocument()) {
        await chrome.offscreen.createDocument({
            url: chrome.runtime.getURL(OFFSCREEN_DOCUMENT_PATH),
            reasons: ['LOCAL_STORAGE'],
            justification: 'Firebase OAuth needs to persist credentials in local storage.',
        });
    }
}

/**
 * Settings page displayed within the popup. It handles user authentication,
 * Google Photos source configuration and Gemini API key management.
 */
function Settings({ onBackToHome = null }) {
  const [user, setUser] = useState(null);
  const [albumUrl, setAlbumUrl] = useState("");
  const [albumUrlDraft, setAlbumUrlDraft] = useState("");
  const [geminiPresent, setGeminiPresent] = useState(false);
  const [editAlbum, setEditAlbum] = useState(false);
  const [editKey, setEditKey] = useState(false);
  const [keyDraft, setKeyDraft] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [savingAlbum, setSavingAlbum] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [loadingSettings, setLoadingSettings] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);
      if (!currentUser) {
        setAlbumUrl("");
        setAlbumUrlDraft("");
        setGeminiPresent(false);
        setLoadingSettings(false);
        setStatusMessage("");
        setErrorMessage("");
        return;
      }

      setLoadingSettings(true);
      try {
        const settings = await makeAuthenticatedRequest("/settings");
        const normalized = settings?.album_url || "";
        setAlbumUrl(normalized);
        setAlbumUrlDraft(normalized);
        setGeminiPresent(Boolean(settings?.gemini_key_set));
        setStatusMessage("");
        setErrorMessage("");
      } catch (error) {
        if (error.status === 404) {
          setAlbumUrl("");
          setAlbumUrlDraft("");
          setGeminiPresent(false);
        } else {
          console.error("Failed to fetch settings:", error);
          setErrorMessage("Unable to load your settings. Please try again.");
        }
      } finally {
        setLoadingSettings(false);
      }
    });
    return () => unsubscribe();
  }, []);

  // Set up a listener for messages from the offscreen document
  useEffect(() => {
    if (typeof chrome === 'undefined' || !chrome.runtime?.onMessage) {
      return undefined;
    }
    const messageListener = (message) => {
      if (message.type === 'firebase-login-success') {
        setStatusMessage('Signed in successfully.');
        setErrorMessage("");
        if (onBackToHome) {
          onBackToHome();
        }
      } else if (message.type === 'firebase-login-failure') {
        setErrorMessage(`Login failed: ${message.payload}`);
      }
    };
    chrome.runtime.onMessage.addListener(messageListener);

    return () => {
      chrome.runtime.onMessage.removeListener(messageListener);
    };
  }, []);

  const handleLogin = async () => {
    if (typeof chrome === 'undefined') {
      setErrorMessage('Chrome APIs unavailable');
      return;
    }
    setStatusMessage('Opening Google login…');
    setErrorMessage("");
    try {
      await createOffscreenDocument();
      chrome.runtime.sendMessage({ type: 'firebase-login' });
    } catch (error) {
      console.error('Failed to open login flow', error);
      setStatusMessage("");
      setErrorMessage('Unable to launch Google sign-in. Please try again.');
    }
  };

  const handleLogout = async () => {
    try {
      await signOut(auth);
      setStatusMessage('Signed out.');
      setErrorMessage("");
    } catch (error) {
      console.error("Error during sign-out:", error);
      setErrorMessage('Unable to sign out, please retry.');
    }
  };

  /**
   * Normalises Google Photos album URLs into the backend-friendly path form.
   */
  const normalizeAlbumPath = (value) => {
    const trimmed = (value || "").trim();
    if (!trimmed) return "";
    try {
      const parsed = new URL(trimmed);
      const path = parsed.pathname
        .replace(/\/+/g, "/")
        .replace(/^\/+/, "")
        .replace(/\/$/, "");
      return path;
    } catch (error) {
      return trimmed.replace(/^\/+/, "").replace(/\/$/, "");
    }
  };

  const saveAlbumUrl = async () => {
    const normalized = normalizeAlbumPath(albumUrlDraft);
    setSavingAlbum(true);
    setStatusMessage("");
    setErrorMessage("");
    try {
      await makeAuthenticatedRequest("/settings/album-url", {
        method: "POST",
        body: JSON.stringify({ album_url: normalized }),
      });
      setAlbumUrl(normalized);
      setAlbumUrlDraft(normalized);
      setEditAlbum(false);
      setStatusMessage('Sources updated.');
    } catch (error) {
      console.error("Failed to save album path", error);
      setErrorMessage('Could not save the source album.');
    } finally {
      setSavingAlbum(false);
    }
  };

  const cancelAlbumEdit = () => {
    setAlbumUrlDraft(albumUrl);
    setEditAlbum(false);
  };

  const saveGeminiKey = async () => {
    const trimmed = keyDraft.trim();
    if (!trimmed) {
      setErrorMessage('Enter a valid API key before saving.');
      return;
    }
    setSavingKey(true);
    setStatusMessage("");
    setErrorMessage("");
    try {
      await makeAuthenticatedRequest("/settings/gemini-key", {
        method: "POST",
        body: JSON.stringify({ api_key: trimmed }),
      });
      setGeminiPresent(true);
      setEditKey(false);
      setKeyDraft("");
      setStatusMessage('API key stored securely.');
    } catch (error) {
      console.error("Failed to store API key", error);
      setErrorMessage('Could not store the API key.');
    } finally {
      setSavingKey(false);
    }
  };

  const cancelKeyEdit = () => {
    setKeyDraft("");
    setEditKey(false);
  };

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        <div className="field">
          <div className="field-label">Signed in</div>
          <div className="field-value">
            <div className="text-[13px] text-neutral-800 truncate">
              {user ? user.email : (loadingSettings ? 'Loading…' : 'Not signed in')}
            </div>
            {user ? (
              <button className="icon-btn" onClick={handleLogout} title="Log out">
                ⎋
              </button>
            ) : (
              <button className="btn" onClick={handleLogin} disabled={Boolean(user)}>
                Log in
              </button>
            )}
          </div>
        </div>

        <div className="field">
          <div className="field-label">Sources</div>
          <div className="field-value">
            <input
              value={editAlbum ? albumUrlDraft : albumUrl}
              onChange={(e) => setAlbumUrlDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && editAlbum) saveAlbumUrl();
              }}
              placeholder="https://photos.google.com/share/..."
              className="input"
              disabled={!editAlbum}
            />
            <div className="flex items-center gap-1">
              {!editAlbum ? (
                <button className="icon-btn" onClick={() => { setAlbumUrlDraft(albumUrl); setEditAlbum(true); }} title="Edit">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                </button>
              ) : (
                <>
                  <button className="icon-btn" onClick={saveAlbumUrl} title="Confirm" style={{ color: '#16a34a' }} disabled={savingAlbum}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                  </button>
                  <button className="icon-btn" onClick={cancelAlbumEdit} title="Cancel" disabled={savingAlbum}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 6-12 12M6 6l12 12"/></svg>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="field">
          <div className="field-label">API key</div>
          <div className="field-value">
            <input
              value={editKey ? keyDraft : (geminiPresent ? "••••••••" : "")}
              onChange={(e) => setKeyDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && editKey) saveGeminiKey();
              }}
              placeholder="sk-..."
              className="input"
              disabled={!editKey}
            />
            <div className="flex items-center gap-1">
              {!editKey ? (
                <button className="icon-btn" onClick={() => { setKeyDraft(""); setEditKey(true); }} title="Edit">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                </button>
              ) : (
                <>
                  <button className="icon-btn" onClick={saveGeminiKey} title="Confirm" style={{ color: '#16a34a' }} disabled={savingKey}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                  </button>
                  <button className="icon-btn" onClick={cancelKeyEdit} title="Cancel" disabled={savingKey}>
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m18 6-12 12M6 6l12 12"/></svg>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {(statusMessage || errorMessage) && (
          <div className="text-xs">
            {statusMessage && <p className="text-emerald-600">{statusMessage}</p>}
            {errorMessage && <p className="text-rose-600">{errorMessage}</p>}
          </div>
        )}
      </div>
    </div>
  );
}

export default Settings;
