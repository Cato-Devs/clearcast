import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const REFRESH_MS = 5 * 60 * 1000;
const RETRY_MS = 30 * 1000;

/** Boundaries, locations, the latest predictions and the current weather, kept up to date. */
export function useWeatherData() {
  const [boundaries, setBoundaries] = useState(null);
  const [locations, setLocations] = useState([]);
  const [runList, setRunList] = useState(null);
  const [currentList, setCurrentList] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let timer;
    let geo = null; // boundaries and locations don't change, so they're only fetched once
    let places = null;

    const load = async () => {
      let complete = false;
      try {
        geo ??= await api("/api/boundaries");
        places ??= await api("/api/locations");
        const [runs, current] = await Promise.all([api("/api/predictions/latest"), api("/api/weather/current")]);
        if (!active) return;
        setBoundaries(geo);
        setLocations(places);
        setRunList(runs);
        setCurrentList(current);
        setFailed(false);
        complete = runs.length >= places.length;
      } catch {
        if (active) setFailed(true);
      }
      // Check again soon after a failure, or while the first predictions are still arriving
      if (active) timer = setTimeout(load, complete ? REFRESH_MS : RETRY_MS);
    };

    load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, []);

  const runs = useMemo(() => Object.fromEntries((runList ?? []).map((r) => [r.location, r])), [runList]);
  const current = useMemo(() => Object.fromEntries((currentList ?? []).map((c) => [c.location, c])), [currentList]);
  const nairobiNames = useMemo(() => (boundaries?.features ?? []).map((f) => f.properties.name), [boundaries]);
  const townNames = useMemo(
    () => locations.map((l) => l.name).filter((name) => !nairobiNames.includes(name)),
    [locations, nairobiNames],
  );
  const latestIssue = useMemo(() => {
    const times = (runList ?? []).flatMap((r) => r.predictions.map((p) => p.issued_at));
    return times.length ? times.reduce((a, b) => (a > b ? a : b)) : null;
  }, [runList]);

  return { boundaries, runs, runList, current, currentList, nairobiNames, townNames, latestIssue, failed };
}
