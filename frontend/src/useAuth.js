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

  /** Log in with a phone number or an email address. */
  const login = useCallback(
    async (phoneOrEmail, password) => {
      finishLogin(await api("/api/auth/login", { method: "POST", body: { login: phoneOrEmail, password } }));
    },
    [finishLogin],
  );

  /** Sign-up, step 1: sends a code by SMS. Returns the number as the server stored it. */
  const startRegister = useCallback(async ({ phone, email, password, homeLocation }) => {
    const body = { phone, email: email.trim() || null, password, home_location: homeLocation || null };
    return (await api("/api/auth/register", { method: "POST", body })).phone;
  }, []);

  /** Sign-up, step 2: the right code creates the account and logs in. */
  const verifyRegister = useCallback(
    async (phone, code) => {
      finishLogin(await api("/api/auth/register/verify", { method: "POST", body: { phone, code } }));
    },
    [finishLogin],
  );

  /** A call that needs a login. An expired login logs out and says why, wherever it happens. */
  const request = useCallback(
    async (path, options = {}) => {
      try {
        return await api(path, { ...options, token });
      } catch (e) {
        if (e.status === 401 && token) endSession();
        throw e;
      }
    },
    [token, endSession],
  );

  const setHome = useCallback(
    async (homeLocation) => {
      setUser(await request("/api/me", { method: "PATCH", body: { home_location: homeLocation } }));
    },
    [request],
  );

  const setEmail = useCallback(
    async (email) => {
      setUser(await request("/api/me/email", { method: "PUT", body: { email: email.trim() || null } }));
    },
    [request],
  );

  /** Changing the phone number: step 1 texts a code to the new number, step 2 checks it. */
  const startPhoneChange = useCallback(
    async (phone) => (await request("/api/me/phone", { method: "POST", body: { phone } })).phone,
    [request],
  );

  const verifyPhoneChange = useCallback(
    async (code) => {
      setUser(await request("/api/me/phone/verify", { method: "POST", body: { code } }));
    },
    [request],
  );

  const logout = useCallback(() => {
    clear();
    setSessionEnded(false);
  }, [clear]);

  return {
    token,
    user,
    sessionEnded,
    login,
    startRegister,
    verifyRegister,
    logout,
    setHome,
    setEmail,
    startPhoneChange,
    verifyPhoneChange,
    request,
  };
}
