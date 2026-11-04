import { useEffect, useMemo, useState } from "react";
import NairobiMap from "./NairobiMap.jsx";
import { BANDS, displayBand, EVENTS, formatEat, isCurrent, NO_DATA } from "./weather.js";

const REFRESH_MS = 5 * 60 * 1000;
const RETRY_MS = 30 * 1000;

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
  return response.json();
}

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
        <button key={e.id} type="button" aria-pressed={e.id === event} onClick={() => onChange(e.id)}>
          {e.label}
        </button>
      ))}
    </div>
  );
}

function LocationDetail({ name, run, event, onEvent }) {
  return (
    <section className="card detail" aria-labelledby="detail-title">
      <h2 id="detail-title">{name}</h2>
      <ul>
        {EVENTS.map((e) => {
          const band = displayBand(run, e.id);
          const prediction = run?.predictions.find((p) => p.event === e.id);
          return (
            <li key={e.id}>
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

function LocationTable({ title, locations, runs, event, selected, onSelect }) {
  return (
    <section className="card">
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

  useEffect(() => {
    let active = true;
    let timer;
    let geo = null; // boundaries and locations don't change, so they're only fetched once
    let places = null;

    const load = async () => {
      let complete = false;
      try {
        geo ??= await getJson("/api/boundaries");
        places ??= await getJson("/api/locations");
        const runs = await getJson("/api/predictions/latest");
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
      </header>

      <p className="notice">
        <strong>Prototype.</strong> These likelihoods have not been validated on live weather data. Don't rely on them
        for safety decisions. Follow official Kenya Meteorological Department warnings.
      </p>

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
        <section className="card map-card" aria-labelledby="map-title">
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

        <LocationDetail name={selected} run={runs[selected]} event={event} onEvent={setEvent} />
      </div>

      <div className="tables">
        <LocationTable
          title="Nairobi constituencies"
          locations={nairobiNames}
          runs={runs}
          event={event}
          selected={selected}
          onSelect={setSelected}
        />
        <LocationTable
          title="Other towns"
          locations={townNames}
          runs={runs}
          event={event}
          selected={selected}
          onSelect={setSelected}
        />
      </div>
    </div>
  );
}
