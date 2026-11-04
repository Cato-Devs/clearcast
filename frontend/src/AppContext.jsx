import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useAuth } from "./useAuth.js";
import { useNotifications } from "./useNotifications.js";
import { useWeatherData } from "./useWeatherData.js";

const AppContext = createContext(null);

export const useApp = () => useContext(AppContext);

/** What every page shares: the login, the weather data, and the current map selection. */
export function AppProvider({ children }) {
  const auth = useAuth();
  const weather = useWeatherData();
  const notifications = useNotifications(auth.token, auth.request);
  const [event, setEvent] = useState("rain");
  const [selected, setSelected] = useState("Westlands");
  const [authMode, setAuthMode] = useState(null); // null, "login" or "register"

  const home = auth.user?.home_location ?? null;

  // Show someone their home location when they log in or come back
  useEffect(() => {
    if (home) setSelected(home);
  }, [home]);

  const value = useMemo(
    () => ({ auth, weather, notifications, event, setEvent, selected, setSelected, authMode, setAuthMode, home }),
    [auth, weather, notifications, event, selected, authMode, home],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
