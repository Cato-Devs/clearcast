import { Link } from "react-router";
import { useApp } from "../AppContext.jsx";
import { EventList, EventPicker, HomeControl, Legend } from "../components.jsx";
import NairobiMap from "../NairobiMap.jsx";
import { EVENTS } from "../weather.js";

export default function MapPage() {
  const { event, selected, setSelected, weather } = useApp();
  const eventInfo = EVENTS.find((e) => e.id === event);

  return (
    <div className="stack">
      {weather.runList?.length === 0 && (
        <p className="notice">The first predictions are being collected. This takes about a minute.</p>
      )}

      <EventPicker />

      <div className="layout">
        <section className={`card map-card event-${event}`} aria-labelledby="map-title">
          <h1 id="map-title" className="card-title">
            {eventInfo.label} across Nairobi
          </h1>
          <p className="hint">{eventInfo.detail}</p>
          <div className="map">
            {weather.boundaries ? (
              <NairobiMap
                boundaries={weather.boundaries}
                runs={weather.runs}
                event={event}
                selected={selected}
                onSelect={setSelected}
              />
            ) : (
              <p className="hint">{weather.failed ? "The map couldn't load." : "Loading map…"}</p>
            )}
          </div>
          <Legend />
        </section>

        <section className="card detail" aria-labelledby="detail-title">
          <div className="detail-head">
            <h2 id="detail-title">{selected}</h2>
            <HomeControl key={selected} name={selected} />
          </div>
          <EventList name={selected} />
          <p className="card-foot">
            <Link className="link small" to={`/locations/${encodeURIComponent(selected)}`}>
              Open {selected}
            </Link>
          </p>
        </section>
      </div>
    </div>
  );
}
