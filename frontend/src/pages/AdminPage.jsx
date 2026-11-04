import { useCallback, useEffect, useState } from "react";
import { useApp } from "../AppContext.jsx";
import { LoginPrompt } from "../components.jsx";
import { EVENTS, formatEat } from "../weather.js";
import NotFoundPage from "./NotFoundPage.jsx";

const TABS = [
  { id: "system", label: "System" },
  { id: "model", label: "Model results" },
  { id: "users", label: "Users" },
  { id: "alerts", label: "Alert log" },
];
const EVENT_LABELS = { ...Object.fromEntries(EVENTS.map((e) => [e.id, e.label])), storm: "Storm (report only)" };
const percent = (value) => (value == null ? "n/a" : `${Math.round(value * 100)}%`);

function useAdminData(path) {
  const { auth } = useApp();
  const request = auth.request;
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await request(path));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [request, path]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, failed, load };
}

function Loading({ failed }) {
  return failed ? (
    <p className="form-error" role="alert">
      Couldn't load this. Try refreshing the page.
    </p>
  ) : (
    <p className="hint">Loading…</p>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function SystemTab() {
  const { data, failed } = useAdminData("/api/admin/overview");
  if (!data) return <Loading failed={failed} />;
  const latest = data.latest_collection;
  const changes = data.band_changes;
  return (
    <div className="stack">
      <div className="stats">
        <Stat label="Users" value={data.users} />
        <Stat label="Active alerts" value={data.active_alerts} />
        <Stat label="Notifications, last 24 hours" value={data.notifications_24h} />
        <Stat label="Failed emails" value={data.emails_failed} />
      </div>

      <section className="card">
        <h2>Latest collection</h2>
        {latest ? (
          <>
            <p>
              {formatEat(latest.finished_at)} EAT: {latest.saved} of {latest.total} locations saved.
            </p>
            {latest.failed.length > 0 && <p className="form-error">Failed: {latest.failed.join(", ")}</p>}
          </>
        ) : (
          <p className="hint">No collection has finished yet.</p>
        )}
        <p>
          {data.stale_locations.length === 0
            ? `All ${data.location_count} locations have recent data.`
            : `No recent data for: ${data.stale_locations.join(", ")}.`}
        </p>
      </section>

      <section className="card">
        <h2>Band stability</h2>
        <p>
          {changes.comparisons === 0
            ? "Not enough collections yet. This needs at least two in the same hour."
            : `${changes.changes} band changes in ${changes.comparisons.toLocaleString("en-KE")} comparisons (${((100 * changes.changes) / changes.comparisons).toFixed(1)}%).`}
        </p>
        <p className="hint">
          How often a location's band for an event changed between collections of the same data hour, over the last 14 days.
          Alerts wait for a band to hold for two collections, so changes like these don't send an alert straight away.
        </p>
      </section>
    </div>
  );
}

function ModelTab() {
  const { data, failed } = useAdminData("/api/admin/model");
  if (!data) return <Loading failed={failed} />;
  const source = data.source_comparison;
  const events = Object.entries(data.evaluation);
  return (
    <div className="stack">
      {[
        { split: "test", title: "Test years, 2023 to 2025" },
        { split: "final", title: "Final holdout, 2026" },
      ].map(({ split, title }) => (
        <section className="card" key={split}>
          <h2>{title}</h2>
          <p className="hint">Measured on ERA5 data. Targets: recall of at least 85% and F1 of at least 80%.</p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Event</th>
                  <th scope="col">Model</th>
                  <th scope="col" className="number">Real events</th>
                  <th scope="col" className="number">Recall</th>
                  <th scope="col" className="number">Precision</th>
                  <th scope="col" className="number">F1</th>
                  <th scope="col" className="number">AUC</th>
                  <th scope="col">Meets targets</th>
                </tr>
              </thead>
              <tbody>
                {events.map(([event, result]) => (
                  <tr key={event}>
                    <td>{EVENT_LABELS[event] ?? event}</td>
                    <td>{result.model_type === "random_forest" ? "Random forest" : "Decision tree"}</td>
                    <td className="number">{result[split].positives.toLocaleString("en-KE")}</td>
                    <td className="number">{percent(result[split].recall)}</td>
                    <td className="number">{percent(result[split].precision)}</td>
                    <td className="number">{percent(result[split].f1)}</td>
                    <td className="number">{result[split].auc_roc?.toFixed(3) ?? "n/a"}</td>
                    <td>{result[split].meets_targets ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <section className="card">
        <h2>ERA5 compared with the data used live</h2>
        <p className="hint">
          {source.period}, {source.locations.toLowerCase()}. {source.description}
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Event</th>
                <th scope="col" className="number">Real events</th>
                <th scope="col" className="number">Caught using ERA5</th>
                <th scope="col" className="number">Caught using Open-Meteo</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(source.events).map(([event, row]) => (
                <tr key={event}>
                  <td>{EVENT_LABELS[event] ?? event}</td>
                  <td className="number">{row.real_events.toLocaleString("en-KE")}</td>
                  <td className="number">{percent(row.caught_era5)}</td>
                  <td className="number">{percent(row.caught_open_meteo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function UsersTab() {
  const { auth } = useApp();
  const { data, failed, load } = useAdminData("/api/admin/users");
  const [error, setError] = useState(null);
  if (!data) return <Loading failed={failed} />;

  const setActive = async (user, isActive) => {
    setError(null);
    try {
      await auth.request(`/api/admin/users/${user.id}`, { method: "PATCH", body: { is_active: isActive } });
      await load();
    } catch (failure) {
      if (failure.status !== 401) setError(failure.message);
    }
  };

  return (
    <section className="card">
      <h2>Users</h2>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Email</th>
              <th scope="col">Home</th>
              <th scope="col" className="number">Active alerts</th>
              <th scope="col">Joined</th>
              <th scope="col">Status</th>
              <th scope="col"><span className="visually-hidden">Action</span></th>
            </tr>
          </thead>
          <tbody>
            {data.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>{user.home_location ?? "None"}</td>
                <td className="number">{user.active_alerts}</td>
                <td>{formatEat(user.created_at)}</td>
                <td>{user.is_admin ? "Admin" : user.is_active ? "Active" : "Disabled"}</td>
                <td>
                  {!user.is_admin && (
                    <button
                      type="button"
                      className="button"
                      aria-label={`${user.is_active ? "Disable" : "Enable"} ${user.email}`}
                      onClick={() => setActive(user, !user.is_active)}
                    >
                      {user.is_active ? "Disable" : "Enable"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const EMAIL_STATUS = { pending: "Sending", sent: "Sent", failed: "Failed", not_configured: "Email not set up" };

function AlertsTab() {
  const { data, failed } = useAdminData("/api/admin/alerts");
  if (!data) return <Loading failed={failed} />;
  return (
    <section className="card">
      <h2>Alert log</h2>
      {data.length === 0 ? (
        <p className="hint">No alerts have been sent yet.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Sent (EAT)</th>
                <th scope="col">User</th>
                <th scope="col">Alert</th>
                <th scope="col">Email</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.id}>
                  <td>{formatEat(row.created_at)}</td>
                  <td>{row.email}</td>
                  <td>{row.title}</td>
                  <td>{row.email_status ? EMAIL_STATUS[row.email_status] : "Not requested"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function AdminPage() {
  const { auth } = useApp();
  const [tab, setTab] = useState("system");

  if (!auth.user) return <LoginPrompt title="Admin">Log in with the admin account to see this page.</LoginPrompt>;
  // The backend also refuses admin data to anyone else: hiding the page is only for convenience
  if (!auth.user.is_admin) return <NotFoundPage />;

  return (
    <div className="stack">
      <h1 className="page-title">Admin</h1>
      <div className="kind-tabs" role="group" aria-label="Admin section">
        {TABS.map((t) => (
          <button key={t.id} type="button" aria-pressed={t.id === tab} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "system" && <SystemTab />}
      {tab === "model" && <ModelTab />}
      {tab === "users" && <UsersTab />}
      {tab === "alerts" && <AlertsTab />}
    </div>
  );
}
