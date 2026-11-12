import { Link } from "react-router";
import { useApp } from "../AppContext.jsx";
import { compass, formatEat, isCurrent, kmh, liveSources, SOURCE_LABEL } from "../weather.js";

const round = (value, places = 0) => Number(value.toFixed(places)).toLocaleString("en-KE");

// Each column shows one or more weather fields. The value is marked as an estimate if any of
// its fields came from Open-Meteo rather than a live reading.
const COLUMNS = [
  { label: "Temperature", fields: ["temperature"], show: (v) => `${round(v.temperature)}°C` },
  { label: "Humidity", fields: ["humidity"], show: (v) => `${round(v.humidity)}%` },
  {
    label: "Wind",
    fields: ["wind_speed", "wind_deg"],
    show: (v) => `${kmh(v.wind_speed)} km/h${v.wind_deg == null ? "" : ` ${compass(v.wind_deg)}`}`,
  },
  { label: "Gusts", fields: ["wind_gust"], show: (v) => `${kmh(v.wind_gust)} km/h` },
  { label: "Rain, last hour", fields: ["rainfall"], show: (v) => `${round(v.rainfall, 1)} mm` },
  { label: "Cloud cover", fields: ["cloud_cover"], show: (v) => `${round(v.cloud_cover)}%` },
  { label: "Pressure", fields: ["pressure"], show: (v) => `${round(v.pressure)} hPa` },
];

function Value({ row, column }) {
  if (column.fields.some((f) => row.values[f] == null && f !== "wind_deg")) return "—";
  const estimated = column.fields.filter((f) => row.sources[f] === "open_meteo");
  const text = column.show(row.values);
  if (estimated.length === 0) return text;
  return (
    <span className="estimate" title={SOURCE_LABEL.open_meteo}>
      ≈ {text}
      <span className="visually-hidden"> (estimate)</span>
    </span>
  );
}

function WeatherTable({ title, locations }) {
  const { weather } = useApp();
  return (
    <section className="card" aria-labelledby={`${title}-heading`}>
      <h2 id={`${title}-heading`}>{title}</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Location</th>
              <th scope="col">Conditions</th>
              {COLUMNS.map((c) => (
                <th key={c.label} scope="col" className="number">
                  {c.label}
                </th>
              ))}
              <th scope="col">Observed (EAT)</th>
              <th scope="col">Data</th>
            </tr>
          </thead>
          <tbody>
            {locations.map((name) => {
              const row = weather.current[name];
              const fresh = row && isCurrent(row);
              return (
                <tr key={name}>
                  <th scope="row">
                    <Link className="link" to={`/locations/${encodeURIComponent(name)}`}>
                      {name}
                    </Link>
                  </th>
                  {fresh ? (
                    <>
                      <td className="conditions">{row.description ?? "—"}</td>
                      {COLUMNS.map((c) => (
                        <td key={c.label} className="number">
                          <Value row={row} column={c} />
                        </td>
                      ))}
                      <td>{formatEat(row.observed_at ?? row.issued_at)}</td>
                      <td>{liveSources(row)}</td>
                    </>
                  ) : (
                    <td colSpan={COLUMNS.length + 3} className="hint">
                      No recent data
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function CurrentWeatherPage() {
  const { weather } = useApp();
  return (
    <div className="stack">
      <h1 className="page-title">Current weather</h1>
      <p className="hint">
        The latest readings, as the prediction models received them. They come from OpenWeather, with Tomorrow.io filling
        any gaps. Values marked ≈ are Open-Meteo estimates, used when neither service reported that value. Updated every
        15 minutes.
      </p>
      {weather.currentList === null ? (
        <p className="hint">Loading…</p>
      ) : (
        <>
          <WeatherTable title="Nairobi constituencies" locations={weather.nairobiNames} />
          <WeatherTable title="Other towns" locations={weather.townNames} />
        </>
      )}
    </div>
  );
}
