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

  return (
    <div className="space-y-5">      
      <div className="space-y-3">
        <div className="field">
          <div className="field-label">Signed in</div>
          <div className="field-value">
            <div className="text-[13px] text-neutral-800 truncate">{userEmail || "Not signed in"}</div>
            <button className="icon-btn" onClick={logout} title="Log out">⎋</button>
          </div>
        </div>

        <div className="field">
          <div className="field-label">Sources</div>
          <div className="field-value">
            <input
              value={editAlbum ? albumUrlDraft : albumUrl}
              onChange={(e) => setAlbumUrlDraft(e.target.value)}
              placeholder="https://photos.app.goo.gl/..."
              className="input"
              disabled={!editAlbum}
            />
            <div className="flex items-center gap-1">
              <button className="icon-btn" onClick={() => setEditAlbum((v) => !v)} title="Edit">✎</button>
              {editAlbum && (
                <button className="icon-btn" onClick={saveAlbumUrl} title="Update">↻</button>
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
              placeholder="sk-..."
              className="input"
              disabled={!editKey}
            />
            <div className="flex items-center gap-1">
              <button className="icon-btn" onClick={() => setEditKey((v) => !v)} title="Edit">✎</button>
              {editKey && (
                <button className="icon-btn" onClick={saveGeminiKey} title="Update">↻</button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


