import { useEffect, useState } from "react";
import extCfg from "../extension-config.json";

export default function Settings() {
  const [userEmail, setUserEmail] = useState("");
  const [albumUrl, setAlbumUrl] = useState("");
  const [albumUrlDraft, setAlbumUrlDraft] = useState("");
  const [geminiPresent, setGeminiPresent] = useState(false);
  const [geminiEnv, setGeminiEnv] = useState("GOOGLE_API_KEY");
  const [editAlbum, setEditAlbum] = useState(false);
  const [editKey, setEditKey] = useState(false);
  const [keyDraft, setKeyDraft] = useState("");
  const serverBase = extCfg.serverBaseUrl;

  useEffect(() => {
    fetch(`${serverBase}/settings`)
      .then((r) => r.json())
      .then((d) => {
        setUserEmail(d.user || "");
        const au = d.album_url || "";
        setAlbumUrl(au);
        setAlbumUrlDraft(au);
        setGeminiPresent(!!d.gemini_key_present);
        setGeminiEnv(d.gemini_key_env || "GOOGLE_API_KEY");
      })
      .catch(() => {});
  }, []);

  async function saveAlbumUrl() {
    await fetch(`${serverBase}/settings/album-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ album_url: albumUrlDraft || albumUrl }),
    });
    if (albumUrlDraft) setAlbumUrl(albumUrlDraft);
    setEditAlbum(false);
  }

  async function saveGeminiKey() {
    if (!keyDraft) return;
    await fetch(`${serverBase}/settings/gemini-key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: keyDraft }),
    });
    setGeminiPresent(true);
    setEditKey(false);
    setKeyDraft("");
  }

  async function logout() {
    await fetch(`${serverBase}/settings/logout`, { method: "POST" });
    setUserEmail("");
  }

  async function login() {
    await fetch(`${serverBase}/auth/login`, { method: "POST" });
    // refresh settings
    const r = await fetch(`${serverBase}/settings`);
    const d = await r.json();
    setUserEmail(d.user || "");
  }

  return (
    <div className="space-y-5">      
      <div className="space-y-3">
        <div className="field">
          <div className="field-label">Signed in</div>
          <div className="field-value">
            <div className="text-[13px] text-neutral-800 truncate">{userEmail || "Not signed in"}</div>
            {userEmail ? (
              <button className="icon-btn" onClick={logout} title="Log out">⎋</button>
            ) : (
              <button className="icon-btn" onClick={login} title="Log in">➤</button>
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
