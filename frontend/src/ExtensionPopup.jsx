import { Search, Settings as Gear, ArrowLeft } from "lucide-react";
import { useState, useEffect } from "react";
import Landing from "./pages/Landing";
import Query from "./pages/Query";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import extCfg from "./extension-config.json";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "./firebase";

export default function ExtensionPopup() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState("landing");
  const serverBase = extCfg.serverBaseUrl;

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        const token = await user.getIdToken();
        // Store the token in a way that's accessible to your API calls
        // For example, in a context or a global state management library.
        // For simplicity here, we can store it in localStorage, though this is not the most secure method for extensions.
        localStorage.setItem('firebaseIdToken', token);
      } else {
        localStorage.removeItem('firebaseIdToken');
      }
    });
    return () => unsubscribe();
  }, []);

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

  async function makeAuthenticatedRequest(url, options = {}) {
    const token = localStorage.getItem('firebaseIdToken');
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
    };
    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      // Attempt to parse error details from the server, but fallback to status text
      let errorDetail = response.statusText;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        // Ignore if the error response is not JSON
      }
      throw new Error(`Request failed: ${response.status} ${errorDetail}`);
    }

    // Handle cases with no content
    if (response.status === 204) {
      return null;
    }

    return response.json();
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
