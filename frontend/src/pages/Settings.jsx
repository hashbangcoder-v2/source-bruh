import React, { useState, useEffect } from "react";
import { auth } from "../firebase";
import { signOut, onAuthStateChanged } from "firebase/auth";
import { LogIn, LogOut, Edit3, Check, X } from "lucide-react";
import extCfg from "../extension-config.json";

// Path to the offscreen document
const OFFSCREEN_DOCUMENT_PATH = '/offscreen.html';

async function hasOffscreenDocument() {
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

async function createOffscreenDocument() {
    if (!await hasOffscreenDocument()) {
        await chrome.offscreen.createDocument({
            url: chrome.runtime.getURL(OFFSCREEN_DOCUMENT_PATH),
            reasons: ['LOCAL_STORAGE'],
            justification: 'Firebase OAuth needs to persist credentials in local storage.',
        });
    }
}

function Settings() {
  const [user, setUser] = useState(null);
  const [albumUrl, setAlbumUrl] = useState("");
  const [albumUrlDraft, setAlbumUrlDraft] = useState("");
  const [geminiPresent, setGeminiPresent] = useState(false);
  const [geminiEnv, setGeminiEnv] = useState("GOOGLE_API_KEY");
  const [editAlbum, setEditAlbum] = useState(false);
  const [editKey, setEditKey] = useState(false);
  const [keyDraft, setKeyDraft] = useState("");
  const serverBase = extCfg.serverBaseUrl;

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      if (currentUser) {
        // Fetch settings from your backend after user is logged in
        const fetchSettings = async () => {
          try {
            const settings = await makeAuthenticatedRequest("/settings");
            if (settings) {
              setAlbumUrl(settings.album_url || "");
              setGeminiKeySet(settings.gemini_key_set || false);
            }
          } catch (error) {
            console.error("Failed to fetch settings:", error);
            // Optionally, show an error to the user
          }
        };
        fetchSettings();
      }
    });
    return () => unsubscribe();
  }, []);

  // Set up a listener for messages from the offscreen document
  useEffect(() => {
      const messageListener = (message) => {
          if (message.type === 'firebase-login-success') {
              console.log('Login successful:', message.payload);
              // The onAuthStateChanged listener will handle the UI update
          } else if (message.type === 'firebase-login-failure') {
              console.error('Login failed:', message.payload);
              // Optionally, show an error message to the user
          }
      };
      chrome.runtime.onMessage.addListener(messageListener);

      return () => {
          chrome.runtime.onMessage.removeListener(messageListener);
      };
  }, []);

  const handleLogin = async () => {
    // Create the offscreen document if it doesn't exist
    await createOffscreenDocument();

    // Send a message to the offscreen document to start the auth flow
    chrome.runtime.sendMessage({ type: 'firebase-login' });
  };

  const handleLogout = async () => {
    try {
      await signOut(auth);
    } catch (error) {
      console.error("Error during sign-out:", error);
    }
  };

  // Placeholder functions for saving data. These will need to be updated.
  const saveAlbumUrl = () => setEditAlbum(false);
  const saveGeminiKey = () => setEditKey(false);

  return (
    <div className="space-y-5">      
      <div className="space-y-3">
        <div className="field">
          <div className="field-label">Signed in</div>
          <div className="field-value">
            <div className="text-[13px] text-neutral-800 truncate">
              {user ? user.email : "Not signed in"}
            </div>
            {user ? (
              <button className="icon-btn" onClick={handleLogout} title="Log out">
                ⎋
              </button>
            ) : (
              <button className="btn" onClick={handleLogin}>
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
              placeholder="https://photos.app.goo.gl/..."
              className="input"
              disabled={!editAlbum}
            />
            <div className="flex items-center gap-1">
              {!editAlbum ? (
                <button className="icon-btn" onClick={() => { setAlbumUrlDraft(albumUrl); setEditAlbum(true); }} title="Edit">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                </button>
              ) : (
                <button className="icon-btn" onClick={saveAlbumUrl} title="Confirm" style={{ color: '#16a34a' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                </button>
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
                <button className="icon-btn" onClick={saveGeminiKey} title="Confirm" style={{ color: '#16a34a' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
