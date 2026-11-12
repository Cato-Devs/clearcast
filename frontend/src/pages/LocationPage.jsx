import { Link, useParams } from "react-router";
import { useApp } from "../AppContext.jsx";
import { EventList, HomeControl } from "../components.jsx";
import { compass, formatEat, isCurrent, kmh, liveSources } from "../weather.js";
import NotFoundPage from "./NotFoundPage.jsx";

/** One line on the weather now, and where the reading came from. */
function CurrentLine({ name }) {
  const { weather } = useApp();
  const row = weather.current[name];
  if (!row || !isCurrent(row)) return null;
  const v = row.values;
  const parts = [
    v.temperature != null && `${Math.round(v.temperature)}°C`,
    row.description,
    v.humidity != null && `${Math.round(v.humidity)}% humidity`,
    v.wind_speed != null && `wind ${kmh(v.wind_speed)} km/h${v.wind_deg == null ? "" : ` ${compass(v.wind_deg)}`}`,
    v.rainfall != null && `${v.rainfall.toFixed(1)} mm rain in the last hour`,
  ].filter(Boolean);
  return (
    <div className="current-line">
      <p>
        <strong>Now:</strong> {parts.join(", ")}
      </p>
      <p className="hint">
        Data: {liveSources(row)}, observed {formatEat(row.observed_at ?? row.issued_at)} EAT.{" "}
        <Link className="link" to="/weather">
          All current weather
        </Link>
      </p>
    </div>
  );
}

export default function LocationPage() {
  const { name } = useParams();
  const { weather } = useApp();
  const known = [...weather.nairobiNames, ...weather.townNames];

  // Wait for the list of locations before saying that one doesn't exist
  if (known.length > 0 && !known.includes(name)) return <NotFoundPage title="Location not found" />;

  return (
    <div className="stack narrow">
      <p>
        <Link className="link small" to="/locations">
          ← All locations
        </Link>
      </p>
      <section className="card detail" aria-labelledby="detail-title">
        <div className="detail-head">
          <h1 id="detail-title" className="card-title">
            {name}
          </h1>
          <HomeControl key={name} name={name} />
        </div>
        <CurrentLine name={name} />
        <EventList name={name} />
        <p className="card-foot">
          <Link className="link small" to={`/alerts?location=${encodeURIComponent(name)}`}>
            Create an alert for {name}
          </Link>
        </p>
      </section>
    </div>
  );
}
