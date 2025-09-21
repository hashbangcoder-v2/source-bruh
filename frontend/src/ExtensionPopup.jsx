import { Search, Settings as Gear, ArrowLeft } from "lucide-react";
import { useState, useEffect } from "react";
import Landing from "./pages/Landing";
import Query from "./pages/Query";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import extCfg from "./extension-config.json";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "./firebase";
import { makeAuthenticatedRequest } from "./api";

export default function ExtensionPopup() {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState("landing");
  const serverBase = extCfg.serverBaseUrl;

  useEffect(() => {
    const hasChrome = typeof chrome !== "undefined" && chrome?.storage?.local;
    if (hasChrome) {
      chrome.storage.local.set({ serverBaseUrl: serverBase });
    }
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        const token = await user.getIdToken();
        // Store the token in a way that's accessible to your API calls
        // For example, in a context or a global state management library.
        // For simplicity here, we can store it in localStorage, though this is not the most secure method for extensions.
        localStorage.setItem('firebaseIdToken', token);
        if (hasChrome) {
          chrome.storage.local.set({ firebaseIdToken: token });
        }
      } else {
        localStorage.removeItem('firebaseIdToken');
        if (hasChrome) {
          chrome.storage.local.remove('firebaseIdToken');
        }
      }
      setUser(user);
    });
    return () => unsubscribe();
  }, []);

  async function onSearch(query) {
    setError("");
    setLoading(true);
    try {
      setView("query");
      const results = await makeAuthenticatedRequest(`/search?q=${query}`);
      setSearchResults(results);
    } catch (error) {
      setError("Failed to search. Is the local server running?");
      setView("query"); // Go back to query view on error
    } finally {
      setLoading(false);
    }
  }

  const checkReadinessAndRoute = async () => {
    try {
      // No need to check local storage for token, auth state is the source of truth
      if (!user) {
        setView("landing");
        return;
      }

      const settings = await makeAuthenticatedRequest("/settings");

      if (settings && settings.album_url && settings.gemini_key_set) {
        setView("query");
      } else {
        setView("landing");
      }
    } catch (error) {
      console.error("Failed to check readiness:", error);
      setView("landing"); // Fallback to landing on error
    }
  };

  function goFromLanding() {
    checkReadinessAndRoute();
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
          <Results results={searchResults} />
        </>
      )}
      {view === "settings" && <Settings />}
    </div>
  );
}
