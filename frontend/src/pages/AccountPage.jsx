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

function ContactForm() {
  const { auth } = useApp();
  const { user } = auth;
  const [phone, setPhone] = useState(user.phone ?? "");
  const [email, setEmail] = useState(user.email ?? "");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await auth.setContact(phone, user.is_admin ? user.email : email);
      setMessage("Saved.");
    } catch (failure) {
      if (failure.status === 401) return;
      setError(Array.isArray(failure.detail) ? "Enter a valid email address, or leave it empty." : errorText(failure));
    }
    setBusy(false);
  };

  return (
    <section className="card">
      <h2>Contact details</h2>
      {!user.phone && !user.is_admin && (
        <p className="form-error" role="alert">
          Add your mobile number to get your alerts by SMS.
        </p>
      )}
      <form className="form" onSubmit={submit}>
        <label>
          Mobile number{user.is_admin ? " (optional)" : ""}
          <input
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            required={!user.is_admin}
            placeholder="0712 345 678"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <small>Every alert is sent here by SMS, and shown in the app.</small>
        </label>
        <label>
          Email {user.is_admin ? "(set in the .env file)" : "(optional)"}
          <input
            type="email"
            autoComplete="email"
            disabled={user.is_admin}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          {!user.is_admin && <small>Needed only if you want some alerts by email too.</small>}
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {message && <p role="status">{message}</p>}
        <div className="dialog-actions start">
          <button type="submit" className="button primary" disabled={busy}>
            Save contact details
          </button>
        </div>
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
        <h2>Your account</h2>
        <p>Logged in as {auth.user.phone ?? auth.user.email}</p>
        <div className="dialog-actions start">
          <button type="button" className="button" onClick={auth.logout}>
            Log out
          </button>
        </div>
      </section>
      <ContactForm />
      <HomeForm />
      <PasswordForm />
    </div>
  );
}
