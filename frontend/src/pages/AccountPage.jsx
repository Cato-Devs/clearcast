import { useState } from "react";
import { useApp } from "../AppContext.jsx";
import { LocationOptions, LoginPrompt } from "../components.jsx";

function errorText(error) {
  if (Array.isArray(error.detail)) return "New passwords must be 8 to 128 characters long.";
  return typeof error.detail === "string" ? error.detail : "Couldn't save. Try again.";
}

function HomeForm() {
  const { auth } = useApp();
  const [status, setStatus] = useState(null);

  const change = async (e) => {
    setStatus(null);
    try {
      await auth.setHome(e.target.value || null);
      setStatus("Saved.");
    } catch (failure) {
      if (failure.status !== 401) setStatus("Couldn't save. Try again.");
    }
  };

  return (
    <section className="card">
      <h2>Home location</h2>
      <form className="form" onSubmit={(e) => e.preventDefault()}>
        <label>
          The map opens on this location
          <select value={auth.user.home_location ?? ""} onChange={change}>
            <option value="">None</option>
            <LocationOptions />
          </select>
        </label>
        {status && <p role="status">{status}</p>}
      </form>
    </section>
  );
}

function PasswordForm() {
  const { auth } = useApp();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await auth.request("/api/me/password", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      setCurrent("");
      setNext("");
      setMessage("Password changed.");
    } catch (failure) {
      if (failure.status !== 401) setError(errorText(failure));
    }
    setBusy(false);
  };

  return (
    <section className="card">
      <h2>Change password</h2>
      <form className="form" onSubmit={submit}>
        <label>
          Current password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>
        <label>
          New password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={128}
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <small>At least 8 characters</small>
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {message && <p role="status">{message}</p>}
        <div className="dialog-actions start">
          <button type="submit" className="button primary" disabled={busy}>
            Change password
          </button>
        </div>
      </form>
    </section>
  );
}

export default function AccountPage() {
  const { auth } = useApp();
  if (!auth.user) return <LoginPrompt title="Account">Log in to change your account settings.</LoginPrompt>;
  return (
    <div className="stack narrow">
      <h1 className="page-title">Account</h1>
      <section className="card">
        <h2>Your details</h2>
        <p>{auth.user.email}</p>
        <div className="dialog-actions start">
          <button type="button" className="button" onClick={auth.logout}>
            Log out
          </button>
        </div>
      </section>
      <HomeForm />
      <PasswordForm />
    </div>
  );
}
