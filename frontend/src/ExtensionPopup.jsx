import { Search, Settings as Gear, ArrowLeft } from "lucide-react";
import { useState, useEffect, useCallback, useMemo } from "react";
import Landing from "./pages/Landing";
import Query from "./pages/Query";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import extCfg from "./extension-config.json";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "./firebase";
import { makeAuthenticatedRequest, authenticatedSearch } from "./api";

/**
 * Root component for the Chrome extension popup. It orchestrates the
 * navigation between the landing (home), query, results and settings
 * experiences while also wiring up Firebase authentication state to the
 * backend.
 */
export default function ExtensionPopup() {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [viewStack, setViewStack] = useState(["landing"]);
  const view = useMemo(() => viewStack[viewStack.length - 1] || "landing", [viewStack]);
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
      setViewStack((stack) => {
        const next = [...stack];
        next[next.length - 1] = "query";
        return next;
      });
      const results = await authenticatedSearch(query);
      setSearchResults(results);
    } catch (error) {
      setError("Failed to search. Is the local server running?");
      setViewStack((stack) => {
        const next = [...stack];
        next[next.length - 1] = "query";
        return next;
      }); // Go back to query view on error
    } finally {
      setLoading(false);
    }
  }

  const checkReadinessAndRoute = useCallback(async () => {
    if (!user) {
      setViewStack(["settings"]);
      return;
    }

    try {
      const settings = await makeAuthenticatedRequest("/settings");
      if (settings?.gemini_key_set) {
        setError("");
        setViewStack(["query"]);
      } else {
        setError("");
        setViewStack(["settings"]);
      }
    } catch (error) {
      console.error("Failed to check readiness:", error);
      setError("");
      setViewStack(["settings"]);
    }
  }, [user]);

  const goFromLanding = useCallback(() => {
    checkReadinessAndRoute();
  }, [checkReadinessAndRoute]);

  const openSettings = useCallback(() => {
    setViewStack((stack) => [...stack, "settings"]);
  }, []);

  const handleBack = useCallback(() => {
    setViewStack((stack) => {
      if (stack.length <= 1) {
        return ["landing"];
      }
      const next = stack.slice(0, -1);
      return next.length ? next : ["landing"];
    });
  }, []);

  return (
    <div className="w-80 p-4 bg-white shadow-lg rounded-lg space-y-4">
      <div className="flex items-center justify-between">
        <div>
          {view !== "landing" && (
            <button className="p-1 hover:bg-gray-100 rounded" onClick={handleBack} aria-label="Back">
              <ArrowLeft className="h-4 w-4" />
            </button>
          )}
        </div>
        <div>
          {view !== "settings" && (
            <button className="p-1 hover:bg-gray-100 rounded" onClick={openSettings} aria-label="Settings">
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
      {view === "settings" && <Settings onBackToHome={() => setViewStack(["landing"])} />}
    </div>
  );
}
