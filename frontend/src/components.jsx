// Pieces used on more than one page.
import { useState } from "react";
import { Link } from "react-router";
import { useApp } from "./AppContext.jsx";
import { BANDS, displayBand, EVENTS, formatEat, isCurrent, NO_DATA } from "./weather.js";

export function Band({ band }) {
  return (
    <span className="band">
      <span className={`swatch band-${band.id}`} aria-hidden="true" />
      {band.label}
    </span>
  );
}

export function Legend() {
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

export function EventPicker() {
  const { event, setEvent } = useApp();
  return (
    <div className="events" role="group" aria-label="Weather event shown">
      {EVENTS.map((e) => (
        <button
          key={e.id}
          type="button"
          className={`event-${e.id}`}
          aria-pressed={e.id === event}
          onClick={() => setEvent(e.id)}
        >
          <span className="event-dot" aria-hidden="true" />
          {e.label}
        </button>
      ))}
    </div>
  );
}

export function HomeControl({ name }) {
  const { auth, setAuthMode } = useApp();
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!auth.user) {
    return (
      <button type="button" className="link small" onClick={() => setAuthMode("login")}>
        Log in to save a home location
      </button>
    );
  }
  if (auth.user.home_location === name) return <span className="home-tag">Your home location</span>;

  const save = async () => {
    setSaving(true);
    setFailed(false);
    try {
      await auth.setHome(name);
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

/** All seven events for one location. */
export function EventList({ name }) {
  const { event, setEvent, weather } = useApp();
  const run = weather.runs[name];
  return (
    <ul className="event-list">
      {EVENTS.map((e) => {
        const band = displayBand(run, e.id);
        const prediction = run?.predictions.find((p) => p.event === e.id);
        return (
          <li key={e.id} className={`event-${e.id}`}>
            <button type="button" aria-pressed={e.id === event} onClick={() => setEvent(e.id)}>
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
  );
}

export function LocationTable({ title, locations }) {
  const { event, weather, home } = useApp();
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
            <tr key={name}>
              <td>
                <Link className="link" to={`/locations/${encodeURIComponent(name)}`}>
                  {name}
                </Link>
                {name === home && <span className="home-tag"> Home</span>}
              </td>
              <td>
                <Band band={displayBand(weather.runs[name], event)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** A dropdown of the 23 locations. */
export function LocationOptions() {
  const { weather } = useApp();
  return (
    <>
      <optgroup label="Nairobi constituencies">
        {weather.nairobiNames.map((name) => (
          <option key={name}>{name}</option>
        ))}
      </optgroup>
      <optgroup label="Other towns">
        {weather.townNames.map((name) => (
          <option key={name}>{name}</option>
        ))}
      </optgroup>
    </>
  );
}

/** Asks someone to log in, for pages that need an account. */
export function LoginPrompt({ title, children }) {
  const { setAuthMode } = useApp();
  return (
    <section className="card prompt">
      <h1>{title}</h1>
      <p>{children}</p>
      <div className="dialog-actions start">
        <button type="button" className="button primary" onClick={() => setAuthMode("register")}>
          Sign up
        </button>
        <button type="button" className="button" onClick={() => setAuthMode("login")}>
          Log in
        </button>
      </div>
    </section>
  );
}
