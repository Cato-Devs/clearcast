import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

const TOKEN_KEY = "clearcast_token";

// Storage can be unavailable, for example in some private windows. Login then lasts until
// the page is reloaded, instead of breaking the page.
function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to do: see readToken
  }
}

export function useAuth() {
  const [token, setToken] = useState(readToken);
  const [user, setUser] = useState(null);
  const [sessionEnded, setSessionEnded] = useState(false);

  const clear = useCallback(() => {
    writeToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const endSession = useCallback(() => {
    clear();
    setSessionEnded(true);
  }, [clear]);

  // Restore the login after a page reload
  useEffect(() => {
    if (!token || user) return;
    let active = true;
    api("/api/me", { token })
      .then((me) => active && setUser(me))
      .catch((e) => active && e.status === 401 && endSession());
    return () => {
      active = false;
    };
  }, [token, user, endSession]);

  const finishLogin = useCallback((result) => {
    writeToken(result.access_token);
    setToken(result.access_token);
    setUser(result.user);
    setSessionEnded(false);
  }, []);

  const login = useCallback(
    async (email, password) => {
      finishLogin(await api("/api/auth/login", { method: "POST", body: { email, password } }));
    },
    [finishLogin],
  );

  const register = useCallback(
    async (email, password, homeLocation) => {
      const body = { email, password, home_location: homeLocation || null };
      finishLogin(await api("/api/auth/register", { method: "POST", body }));
    },
    [finishLogin],
  );

  const setHome = useCallback(
    async (homeLocation) => {
      try {
        const body = { home_location: homeLocation };
        setUser(await api("/api/me", { method: "PATCH", token, body }));
      } catch (e) {
        if (e.status === 401) endSession();
        else throw e;
      }
    },
    [token, endSession],
  );

  const logout = useCallback(() => {
    clear();
    setSessionEnded(false);
  }, [clear]);

  return { user, sessionEnded, login, register, logout, setHome };
}
