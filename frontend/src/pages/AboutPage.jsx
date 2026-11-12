import { useEffect, useState } from "react";
import { api } from "../api.js";
import { BANDS, EVENTS } from "../weather.js";

const percent = (value) => `${Math.round(value * 100)}%`;

function ReliabilityTable({ data }) {
  return (
    <table>
      <thead>
        <tr>
          <th scope="col">Event</th>
          <th scope="col" className="number">
            Real events
          </th>
          <th scope="col" className="number">
            Caught, using the training data source
          </th>
          <th scope="col" className="number">
            Caught, using the data ClearCast runs on
          </th>
        </tr>
      </thead>
      <tbody>
        {EVENTS.map((e) => {
          const source = data.source_comparison.events[e.id];
          return (
            <tr key={e.id}>
              <td>{e.label}</td>
              <td className="number">{source.real_events.toLocaleString("en-KE")}</td>
              <td className="number">{percent(source.caught_era5)}</td>
              <td className="number">{percent(source.caught_open_meteo)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function AboutPage() {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api("/api/about")
      .then((about) => active && setData(about))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="stack narrow prose">
      <h1 className="page-title">About ClearCast</h1>

      <section className="card">
        <h2>What it does</h2>
        <p>
          ClearCast estimates how likely seven weather events are in the next 6 hours (24 hours for flood risk), for 17
          Nairobi constituencies and 6 other Kenyan towns.
        </p>
        <p>Each event has its own machine learning model, trained on hourly ERA5 weather data from 2010 to 2021.</p>
      </section>

      <section className="card">
        <h2>What the likelihoods mean</h2>
        <ul>
          {BANDS.map((b) => (
            <li key={b.id}>
              <strong>{b.label}</strong>
              {b.id === "very_unlikely" && ": the model's score is less than half the Likely level."}
              {b.id === "unlikely" && ": the score is below the Likely level, but at least half of it."}
              {b.id === "likely" && ": set to catch most real events, so it also raises many false alarms."}
              {b.id === "very_likely" && ": a stricter level, aimed at being right at least 80% of the time."}
            </li>
          ))}
        </ul>
        <p>Each event has its own levels, so the bands are the thing to compare, not the underlying numbers.</p>
      </section>

      <section className="card">
        <h2>Where the data comes from</h2>
        <p>
          The latest predictions use the current reading from OpenWeather, with Tomorrow.io filling any gaps, and the hours before it from Open-Meteo. Past weather for training came from ERA5,
          through the Open-Meteo archive. Constituency boundaries are from geoBoundaries (IEBC and OCHA), and the base map
          is from OpenStreetMap.
        </p>
      </section>

      <section className="card">
        <h2>How far to trust it</h2>
        <p>
          ClearCast's predictions have not been validated against live weather. Please follow Kenya Meteorological
          Department warnings for safety decisions.
        </p>
        <p>
          The models learned from ERA5 data but currently run on forecast-model data, and they catch noticeably fewer
          events on it. Flood risk is affected most.
        </p>
        {data && (
          <>
            <ReliabilityTable data={data} />
            <p className="hint">
              "Caught" is the share of real events rated Likely or above. Both columns cover the same hours, from{" "}
              {data.source_comparison.period}, at the 7 towns used for training, and count ERA5's record as what really
              happened. ERA5 isn't perfect and this period is short, so treat these as a guide. Events with few real cases,
              like Cold, are especially uncertain.
            </p>
          </>
        )}
        {failed && <p className="hint">The reliability figures couldn't load.</p>}
        <p>
          Constituencies can also share weather data, so neighbouring ones may always show the same result, and rainfall
          can vary more than this data can show.
        </p>
      </section>
    </div>
  );
}
