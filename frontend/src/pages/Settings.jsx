import React, { useState, useEffect, useCallback } from "react";
import { auth, db } from "../firebase";
import { signOut, onAuthStateChanged } from "firebase/auth";
import { doc, serverTimestamp, setDoc } from "firebase/firestore";
import { makeAuthenticatedRequest, getServerBaseUrl, checkBackendHealth } from "../api";

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
  const [albumSource, setAlbumSource] = useState("");
  const [albumSourceDraft, setAlbumSourceDraft] = useState("");
  const [geminiPresent, setGeminiPresent] = useState(false);
  const [editAlbum, setEditAlbum] = useState(false);
  const [editKey, setEditKey] = useState(false);
  const [keyDraft, setKeyDraft] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [savingAlbum, setSavingAlbum] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [serverBaseUrl, setServerBaseUrl] = useState("");
  const [checkingServer, setCheckingServer] = useState(false);
  const [serverStatus, setServerStatus] = useState(null);

  const persistUserProfile = useCallback(async (firebaseUser) => {
    if (!firebaseUser) {
      return;
    }
    try {
      const userRef = doc(db, "users", firebaseUser.uid);
      await setDoc(
        userRef,
        {
          user_info: {
            email: firebaseUser.email || "",
            displayName: firebaseUser.displayName || "",
            photoURL: firebaseUser.photoURL || "",
          },
          lastLoginAt: serverTimestamp(),
        },
        { merge: true }
      );
    } catch (error) {
      console.error("Failed to persist user profile", error);
    }
    }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const base = await getServerBaseUrl();
        if (mounted) {
          setServerBaseUrl(base);
        }
      } catch (error) {
        console.warn("Unable to determine server URL", error);
      }
    })();

    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);
      if (!currentUser) {
        setAlbumSource("");
        setAlbumSourceDraft("");
        setGeminiPresent(false);
        setLoadingSettings(false);
        setStatusMessage("");
        setErrorMessage("");
        return;
      }

      setLoadingSettings(true);
      try {
        await persistUserProfile(currentUser);
        const settings = await makeAuthenticatedRequest("/settings");
        const normalized = (settings?.album_title || settings?.album_url || "").trim();
        setAlbumSource(normalized);
        setAlbumSourceDraft(normalized);
        setGeminiPresent(Boolean(settings?.gemini_key_set));
        setStatusMessage("");
        setErrorMessage("");
      } catch (error) {
        if (error.status === 404) {
          setAlbumSource("");
          setAlbumSourceDraft("");
          setGeminiPresent(false);
        } else {
          console.error("Failed to fetch settings:", error);
          setErrorMessage("Unable to load your settings. Please try again.");
        }
      } finally {
        setLoadingSettings(false);
      }
    });
    return () => {
      mounted = false;
      unsubscribe();
    };
  }, [persistUserProfile]);

  // Set up a listener for messages from the offscreen document
  useEffect(() => {
    if (typeof chrome === 'undefined' || !chrome.runtime?.onMessage) {
      return undefined;
    }
    const messageListener = (message) => {
      if (message.type === 'firebase-login-success') {
        setStatusMessage('Signed in successfully.');
        setErrorMessage("");
        if (auth.currentUser) {
          persistUserProfile(auth.currentUser);
        }
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
  }, [persistUserProfile, onBackToHome]);

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
   * Normalises user input so album names remain intact while URLs are reduced
   * to the path fragment expected by the backend.
   */
  const normalizeAlbumInput = (value) => {
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

  const saveAlbumSource = async () => {
    const normalized = normalizeAlbumInput(albumSourceDraft);
    setSavingAlbum(true);
    setStatusMessage("");
    setErrorMessage("");
    try {
      const response = await makeAuthenticatedRequest("/settings/album-url", {
        method: "POST",
        body: JSON.stringify({ album_url: normalized }),
      });
      const savedTitle = response?.album_title || "";
      const savedUrl = response?.album_url || "";
      const nextValue = savedTitle || savedUrl || normalized;
      setAlbumSource(nextValue);
      setAlbumSourceDraft(nextValue);
      setEditAlbum(false);
      setStatusMessage('Sources updated.');
    } catch (error) {
      console.error("Failed to save album path", error);
      if (error?.status === 404 && error?.url) {
        setErrorMessage(`Could not reach ${error.url}. Check that the deployed functions URL is correct.`);
      } else {
        setErrorMessage('Could not save the source album.');
      }
    } finally {
      setSavingAlbum(false);
    }
  };

  const cancelAlbumEdit = () => {
    setAlbumSourceDraft(albumSource);
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
      if (error?.status === 404 && error?.url) {
        setErrorMessage(`Could not reach ${error.url}. Check that the deployed functions URL is correct.`);
      } else {
        setErrorMessage('Could not store the API key.');
      }
    } finally {
      setSavingKey(false);
    }
  };

  const cancelKeyEdit = () => {
    setKeyDraft("");
    setEditKey(false);
  };

  const handleVerifyServer = async () => {
    setCheckingServer(true);
    setServerStatus(null);
    const result = await checkBackendHealth();
    setCheckingServer(false);
    setServerStatus(result);
    if (result.ok) {
      setStatusMessage(`Backend reachable at ${result.baseUrl}.`);
      setErrorMessage("");
    } else {
      setErrorMessage(`Backend at ${result.baseUrl} is not reachable. ${result.error?.message || ''}`.trim());
    }
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
              value={editAlbum ? albumSourceDraft : albumSource}
              onChange={(e) => setAlbumSourceDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && editAlbum) saveAlbumSource();
              }}
              placeholder="Google Photos album link or name"
              className="input"
              disabled={!editAlbum}
            />
            <div className="flex items-center gap-1">
              {!editAlbum ? (
                <button className="icon-btn" onClick={() => { setAlbumSourceDraft(albumSource); setEditAlbum(true); }} title="Edit">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                </button>
              ) : (
                <>
                  <button className="icon-btn" onClick={saveAlbumSource} title="Confirm" style={{ color: '#16a34a' }} disabled={savingAlbum}>
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

      <div className="space-y-2 border-t border-neutral-200 pt-3 text-xs text-neutral-600">
        <div className="font-medium text-neutral-700">Backend</div>
        <div className="flex items-center justify-between gap-2">
          <span className="truncate" title={serverBaseUrl || 'Unknown backend'}>
            {serverBaseUrl || 'Backend URL unavailable'}
          </span>
          <button className="btn" onClick={handleVerifyServer} disabled={checkingServer}>
            {checkingServer ? 'Checking…' : 'Verify connection'}
          </button>
        </div>
        {serverStatus && !serverStatus.ok && (
          <p className="text-rose-600">
            Unable to contact the backend. Confirm that the Firebase Function URL above is correct and deployed.
          </p>
        )}
      </div>
    </div>
  );
}

export default Settings;
