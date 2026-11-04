import { useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import AuthDialog from "./AuthDialog.jsx";
import NairobiMap from "./NairobiMap.jsx";
import { useAuth } from "./useAuth.js";
import { BANDS, displayBand, EVENTS, formatEat, isCurrent, NO_DATA } from "./weather.js";

const REFRESH_MS = 5 * 60 * 1000;
const RETRY_MS = 30 * 1000;

function Band({ band }) {
  return (
    <span className="band">
      <span className={`swatch band-${band.id}`} aria-hidden="true" />
      {band.label}
    </span>
  );
}

function Legend() {
  return (
    <ul className="legend" aria-label="Map legend">
      {[...BANDS, NO_DATA].map((band) => (
        <li key={band.id}>
          <Band band={band} />
        </li>
      ))}
    </ul>
  );
}

function EventPicker({ event, onChange }) {
  return (
    <div className="events" role="group" aria-label="Weather event shown">
      {EVENTS.map((e) => (
        <button
          key={e.id}
          type="button"
          className={`event-${e.id}`}
          aria-pressed={e.id === event}
          onClick={() => onChange(e.id)}
        >
          <span className="event-dot" aria-hidden="true" />
          {e.label}
        </button>
      ))}
    </div>
  );
}

function HomeControl({ name, user, onSetHome, onLogin }) {
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!user) {
    return (
      <button type="button" className="link" onClick={onLogin}>
        Log in to save a home location
      </button>
    );
  }
  if (user.home_location === name) return <span className="home-tag">Your home location</span>;

  const save = async () => {
    setSaving(true);
    setFailed(false);
    try {
      await onSetHome(name);
    } catch {
      setFailed(true);
    }
    setSaving(false);
  };

  return (
    <span className="home-control">
      {failed && (
        <small role="alert" className="form-error">
          Couldn't save. Try again.
        </small>
      )}
      <button type="button" className="button" disabled={saving} onClick={save}>
        Set as home
      </button>
    </span>
  );
}

function LocationDetail({ name, run, event, onEvent, user, onSetHome, onLogin }) {
  return (
    <section className="card detail" aria-labelledby="detail-title">
      <div className="detail-head">
        <h2 id="detail-title">{name}</h2>
        <HomeControl key={name} name={name} user={user} onSetHome={onSetHome} onLogin={onLogin} />
      </div>
      <ul>
        {EVENTS.map((e) => {
          const band = displayBand(run, e.id);
          const prediction = run?.predictions.find((p) => p.event === e.id);
          return (
            <li key={e.id} className={`event-${e.id}`}>
              <button type="button" aria-pressed={e.id === event} onClick={() => onEvent(e.id)}>
                <span className="detail-name">
                  <strong>{e.label}</strong>
                  <small>{e.detail}</small>
                </span>
                <span className="detail-band">
                  <Band band={band} />
                  {prediction && isCurrent(prediction) && <small>until {formatEat(prediction.valid_to)}</small>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function LocationTable({ title, locations, runs, event, selected, onSelect, home }) {
  return (
    <section className={`card event-${event}`}>
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">Location</th>
            <th scope="col">{EVENTS.find((e) => e.id === event).label}</th>
          </tr>
        </thead>
        <tbody>
          {locations.map((name) => (
            <tr key={name} className={name === selected ? "selected" : undefined}>
              <td>
                <button type="button" className="link" onClick={() => onSelect(name)}>
                  {name}
                </button>
                {name === home && <span className="home-tag"> Home</span>}
              </td>
              <td>
                <Band band={displayBand(runs[name], event)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function App() {
  const [event, setEvent] = useState("rain");
  const [selected, setSelected] = useState("Westlands");
  const [boundaries, setBoundaries] = useState(null);
  const [locations, setLocations] = useState([]);
  const [runList, setRunList] = useState(null);
  const [failed, setFailed] = useState(false);
  const [authMode, setAuthMode] = useState(null); // null, "login" or "register"
  const auth = useAuth();
  const home = auth.user?.home_location ?? null;

  // Show someone their home location when they log in or come back
  useEffect(() => {
    if (home) setSelected(home);
  }, [home]);

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
        const runs = await api("/api/predictions/latest");
        if (!active) return;
        setBoundaries(geo);
        setLocations(places);
        setRunList(runs);
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

  const nairobiNames = useMemo(
    () => (boundaries?.features ?? []).map((f) => f.properties.name),
    [boundaries],
  );
  const townNames = useMemo(
    () => locations.map((l) => l.name).filter((name) => !nairobiNames.includes(name)),
    [locations, nairobiNames],
  );

  const latestIssue = useMemo(() => {
    const times = (runList ?? []).flatMap((r) => r.predictions.map((p) => p.issued_at));
    return times.length ? times.reduce((a, b) => (a > b ? a : b)) : null;
  }, [runList]);

  const eventInfo = EVENTS.find((e) => e.id === event);

  return (
    <div className="page">
      <header>
        <h1>ClearCast</h1>
        <p className="updated">{latestIssue ? `Weather data to ${formatEat(latestIssue)} EAT` : "Waiting for data"}</p>
        <div className="account">
          {auth.user ? (
            <>
              <span className="account-email">{auth.user.email}</span>
              <button type="button" className="button" onClick={auth.logout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <button type="button" className="button" onClick={() => setAuthMode("login")}>
                Log in
              </button>
              <button type="button" className="button primary" onClick={() => setAuthMode("register")}>
                Sign up
              </button>
            </>
          )}
        </div>
      </header>

      {auth.sessionEnded && (
        <p className="notice" role="status">
          Your login has expired. Log in again to use your account.
        </p>
      )}

      {failed && (
        <p className="notice error" role="alert">
          Couldn't reach the ClearCast server. {runList ? "Showing the last data received." : "Trying again shortly."}
        </p>
      )}

      {runList && runList.length === 0 && (
        <p className="notice">The first predictions are being collected. This takes about a minute.</p>
      )}

      <EventPicker event={event} onChange={setEvent} />

      <div className="layout">
        <section className={`card map-card event-${event}`} aria-labelledby="map-title">
          <h2 id="map-title">{eventInfo.label} across Nairobi</h2>
          <p className="hint">{eventInfo.detail}</p>
          <div className="map">
            {boundaries ? (
              <NairobiMap
                boundaries={boundaries}
                runs={runs}
                event={event}
                selected={selected}
                onSelect={setSelected}
              />
            ) : (
              <p className="hint">{failed ? "The map couldn't load." : "Loading map…"}</p>
            )}
          </div>
          <Legend />
        </section>

        <LocationDetail
          name={selected}
          run={runs[selected]}
          event={event}
          onEvent={setEvent}
          user={auth.user}
          onSetHome={auth.setHome}
          onLogin={() => setAuthMode("login")}
        />
      </div>

      <div className="tables">
        <LocationTable
          title="Nairobi constituencies"
          locations={nairobiNames}
          runs={runs}
          event={event}
          selected={selected}
          onSelect={setSelected}
          home={home}
        />
        <LocationTable
          title="Other towns"
          locations={townNames}
          runs={runs}
          event={event}
          selected={selected}
          onSelect={setSelected}
          home={home}
        />
      </div>

      {authMode && (
        <AuthDialog
          mode={authMode}
          onModeChange={setAuthMode}
          onClose={() => setAuthMode(null)}
          auth={auth}
          nairobiNames={nairobiNames}
          townNames={townNames}
        />
      )}
    </div>
  );
}
