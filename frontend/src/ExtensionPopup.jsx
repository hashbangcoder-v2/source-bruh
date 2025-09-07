import { Search, Settings as Gear, ArrowLeft } from "lucide-react";
import { useState } from "react";
import Landing from "./pages/Landing";
import Query from "./pages/Query";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import extCfg from "./extension-config.json";

export default function ExtensionPopup() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState("landing");
  const serverBase = extCfg.serverBaseUrl;

  async function onSearch() {
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams({ q: query, top_k: "20" });
      const resp = await fetch(`${serverBase}/search?${params.toString()}`);
      if (!resp.ok) throw new Error(`Search failed: ${resp.status}`);
      const data = await resp.json();
      setResults(data);
    } catch (e) {
      setError("Failed to search. Is the local server running?");
    } finally {
      setLoading(false);
    }
  }

  function goFromLanding() {
    // Require auth + sources + key. If missing, go to settings first.
    checkReadinessAndRoute();
  }

  async function checkReadinessAndRoute(direction = "forward") {
    try {
      const r = await fetch(`${serverBase}/settings`);
      const s = await r.json();
      const ready = Boolean(s.user) && Boolean(s.album_url) && Boolean(s.gemini_key_present);
      if (direction === "back") {
        setView(ready ? "query" : "landing");
      } else {
        setView(ready ? "query" : "settings");
      }
    } catch (e) {
      // If server not reachable, assume not ready.
      setView(direction === "back" ? "landing" : "settings");
    }
  }

  return (
    <div className="w-80 p-4 bg-white shadow-lg rounded-lg space-y-4">
      <div className="flex items-center justify-between">
        <div>
          {view !== "landing" && (
            <button className="p-1 hover:bg-gray-100 rounded" onClick={() => checkReadinessAndRoute("back")} aria-label="Back">
              <ArrowLeft className="h-4 w-4" />
            </button>
          )}
        </div>
        <div>
          {view !== "settings" && (
            <button className="p-1 hover:bg-gray-100 rounded" onClick={() => setView("settings")} aria-label="Settings">
              <Gear className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
      {view === "landing" && <Landing onGetStarted={goFromLanding} />}
      {view === "query" && (
        <>
          <Query query={query} setQuery={setQuery} onSearch={onSearch} loading={loading} />
          {error && <div className="text-red-600 text-sm">{error}</div>}
          <Results results={results} />
        </>
      )}
      {view === "settings" && <Settings />}
    </div>
  );
}
