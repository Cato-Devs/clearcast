import { useCallback, useEffect, useState } from "react";
import { useLocation, useSearchParams } from "react-router";
import { api } from "../api.js";
import { useApp } from "../AppContext.jsx";
import { LocationOptions, LoginPrompt } from "../components.jsx";
import { EVENTS, formatEat } from "../weather.js";

const KINDS = [
  { id: "always", label: "Always-on alert", help: "Tells you whenever an event becomes likely at a location." },
  { id: "daily", label: "Daily check", help: "Sends a summary of the next 6 hours at a set time each day, even if all is clear." },
  { id: "trip", label: "Trip check", help: "Checks one place and time, then tells you again if the outlook gets worse." },
];
const BAND_LABEL = { likely: "Likely or above", very_likely: "Very likely only" };

function errorText(error) {
  return typeof error.detail === "string" ? error.detail : "Check the form and try again.";
}

/** The current East Africa Time, in the format a date and time box uses. */
function nowInEat() {
  return new Date(Date.now() + 3 * 3600 * 1000).toISOString().slice(0, 16);
}

function NewAlertForm({ onCreated, emailEnabled }) {
  const { auth, event, home } = useApp();
  const [params] = useSearchParams();
  const [kind, setKind] = useState("always");
  const [location, setLocation] = useState(params.get("location") ?? home ?? "Westlands");
  const [eventId, setEventId] = useState(event);
  const [minBand, setMinBand] = useState("likely");
  const [time, setTime] = useState("06:30");
  const [trip, setTrip] = useState("");
  const [email, setEmail] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(null);
    const body = { kind, location, email };
    if (kind === "always") Object.assign(body, { event: eventId, min_band: minBand });
    if (kind === "daily") body.time_of_day = time;
    // The form is in East Africa Time, wherever the browser is
    if (kind === "trip") body.trip_at = `${trip}:00+03:00`;
    try {
      const created = await auth.request("/api/subscriptions", { method: "POST", body });
      onCreated();
      if (created.kind === "trip") {
        const soon = new Date(created.first_check_at) <= new Date();
        setSaved(soon ? "Saved. We'll check this within a minute." : `Saved. We'll check this on ${formatEat(created.first_check_at)} EAT.`);
      } else {
        setSaved("Saved.");
      }
    } catch (failure) {
      if (failure.status !== 401) setError(errorText(failure));
    }
    setBusy(false);
  };

  return (
    <section className="card" aria-labelledby="new-alert">
      <h2 id="new-alert">New alert</h2>
      <div className="kind-tabs" role="group" aria-label="Type of alert">
        {KINDS.map((k) => (
          <button key={k.id} type="button" aria-pressed={k.id === kind} onClick={() => setKind(k.id)}>
            {k.label}
          </button>
        ))}
      </div>
      <p className="hint">{KINDS.find((k) => k.id === kind).help}</p>

      <form className="form" onSubmit={submit}>
        <label>
          Location
          <select value={location} onChange={(e) => setLocation(e.target.value)}>
            <LocationOptions />
          </select>
        </label>

        {kind === "always" && (
          <>
            <label>
              Weather event
              <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
                {EVENTS.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Alert me at
              <select value={minBand} onChange={(e) => setMinBand(e.target.value)}>
                {Object.entries(BAND_LABEL).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        {kind === "daily" && (
          <label>
            Time (East Africa Time)
            <input type="time" required value={time} onChange={(e) => setTime(e.target.value)} />
          </label>
        )}

        {kind === "trip" && (
          <label>
            Date and time (East Africa Time)
            <input
              type="datetime-local"
              required
              min={nowInEat()}
              value={trip}
              onChange={(e) => setTrip(e.target.value)}
            />
            <small>
              Predictions only reach 6 hours ahead, so we check this about 6 hours before the time you choose. You can
              set it up to 30 days ahead.
            </small>
          </label>
        )}

        <label className="checkbox">
          <input type="checkbox" disabled={!emailEnabled} checked={email} onChange={(e) => setEmail(e.target.checked)} />
          <span>
            Also send by email
            {!emailEnabled && <small> (email isn't set up yet, so this alert will appear in the app)</small>}
          </span>
        </label>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {saved && <p role="status">{saved}</p>}

        <div className="dialog-actions start">
          <button type="submit" className="button primary" disabled={busy}>
            Create alert
          </button>
        </div>
      </form>
    </section>
  );
}

/** A one-line summary of an alert. Also used on the Admin page. */
export function describe(subscription) {
  if (subscription.kind === "always") {
    const event = EVENTS.find((e) => e.id === subscription.event).label;
    return `${event} in ${subscription.location}: ${BAND_LABEL[subscription.min_band].toLowerCase()}`;
  }
  if (subscription.kind === "daily") return `${subscription.location}, every day at ${subscription.time_of_day} EAT`;
  return `${subscription.location}, ${formatEat(subscription.trip_at)} EAT`;
}

function tripStatus(subscription) {
  if (!subscription.active) return "Finished";
  if (subscription.checked) return "Checked. We'll tell you if it gets worse.";
  return `First check: ${formatEat(subscription.first_check_at)} EAT`;
}

function AlertList({ subscriptions, onChange }) {
  const { auth } = useApp();
  const [error, setError] = useState(null);

  const act = async (path, options) => {
    setError(null);
    try {
      await auth.request(path, options);
      onChange();
    } catch (failure) {
      if (failure.status !== 401) setError(errorText(failure));
    }
  };

  return (
    <section className="card" aria-labelledby="your-alerts">
      <h2 id="your-alerts">Your alerts</h2>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {subscriptions.length === 0 ? (
        <p className="hint">You don't have any alerts yet.</p>
      ) : (
        <ul className="rows">
          {subscriptions.map((s) => (
            <li key={s.id} className={s.active ? undefined : "muted"}>
              <span className="row-text">
                <strong>{describe(s)}</strong>
                <small>
                  {KINDS.find((k) => k.id === s.kind).label}
                  {s.email ? " · also by email" : ""}
                  {s.kind === "trip" ? ` · ${tripStatus(s)}` : !s.active ? " · Paused" : ""}
                </small>
              </span>
              <span className="row-actions">
                {(s.kind !== "trip" || s.active) && (
                  <button
                    type="button"
                    className="button"
                    onClick={() =>
                      act(`/api/subscriptions/${s.id}`, { method: "PATCH", body: { active: !s.active } })
                    }
                  >
                    {s.active ? "Pause" : "Resume"}
                  </button>
                )}
                <button
                  type="button"
                  className="button"
                  aria-label={`Delete: ${describe(s)}`}
                  onClick={() => act(`/api/subscriptions/${s.id}`, { method: "DELETE" })}
                >
                  Delete
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function NotificationList() {
  const { notifications } = useApp();
  return (
    <section className="card" id="notifications" aria-labelledby="notifications-title">
      <div className="detail-head">
        <h2 id="notifications-title">Notifications</h2>
        {notifications.unread > 0 && (
          <button type="button" className="button" onClick={() => notifications.markAllRead().catch(() => {})}>
            Mark all as read
          </button>
        )}
      </div>
      {notifications.notifications.length === 0 ? (
        <p className="hint">Nothing yet. Your alerts will appear here.</p>
      ) : (
        <ul className="rows">
          {notifications.notifications.map((n) => (
            <li key={n.id} className={n.read ? "muted" : "unread"}>
              <span className="row-text">
                <strong>
                  {n.read ? "" : <span className="visually-hidden">Unread: </span>}
                  {n.title}
                </strong>
                <span>{n.body}</span>
                <small>{formatEat(n.created_at)} EAT</small>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function AlertsPage() {
  const { auth } = useApp();
  const { hash } = useLocation();
  const [subscriptions, setSubscriptions] = useState([]);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [failed, setFailed] = useState(false);
  const request = auth.request;
  const loggedIn = Boolean(auth.user);

  const load = useCallback(async () => {
    try {
      setSubscriptions(await request("/api/subscriptions"));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [request]);

  useEffect(() => {
    if (!loggedIn) return;
    load();
    api("/api/alert-options")
      .then((options) => setEmailEnabled(options.email_enabled))
      .catch(() => {});
  }, [loggedIn, load]);

  useEffect(() => {
    if (loggedIn && hash === "#notifications") document.getElementById("notifications")?.scrollIntoView();
  }, [loggedIn, hash]);

  if (!auth.user) {
    return (
      <LoginPrompt title="My Alerts">
        Create an account to get alerts for the places you care about, a daily check, or a check before a trip.
      </LoginPrompt>
    );
  }

  return (
    <div className="stack">
      <h1 className="page-title">My Alerts</h1>
      {failed && (
        <p className="notice error" role="alert">
          Couldn't load your alerts. Try refreshing the page.
        </p>
      )}
      <div className="columns">
        <div className="stack">
          <NewAlertForm onCreated={load} emailEnabled={emailEnabled} />
          <AlertList subscriptions={subscriptions} onChange={load} />
        </div>
        <NotificationList />
      </div>
    </div>
  );
}
