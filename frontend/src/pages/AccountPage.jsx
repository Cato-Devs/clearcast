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

function PhoneForm() {
  const { auth } = useApp();
  const { user } = auth;
  const [phone, setPhone] = useState("");
  const [codeFor, setCodeFor] = useState(null); // the new number a code was sent to
  const [code, setCode] = useState("");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (action) => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await action();
    } catch (failure) {
      if (failure.status !== 401) setError(errorText(failure));
    }
    setBusy(false);
  };

  const sendCode = () =>
    run(async () => {
      const sentTo = await auth.startPhoneChange(phone);
      setCodeFor(sentTo);
      setCode("");
      setMessage(`We sent a 6-digit code by SMS to ${sentTo}.`);
    });

  const confirm = (e) => {
    e.preventDefault();
    run(async () => {
      await auth.verifyPhoneChange(code);
      setCodeFor(null);
      setPhone("");
      setMessage("Mobile number changed.");
    });
  };

  return (
    <section className="card">
      <h2>Mobile number</h2>
      {user.phone ? (
        <p>
          Alerts are sent by SMS to <strong>{user.phone}</strong>.
        </p>
      ) : (
        !user.is_admin && (
          <p className="form-error" role="alert">
            Add your mobile number to get your alerts by SMS.
          </p>
        )
      )}
      {codeFor ? (
        <form className="form" onSubmit={confirm}>
          <label>
            Code sent to {codeFor}
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
            <small>It expires in 10 minutes.</small>
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <div className="dialog-actions start">
            <button type="submit" className="button primary" disabled={busy}>
              Confirm
            </button>
            <button type="button" className="button" disabled={busy} onClick={sendCode}>
              Send a new code
            </button>
            <button type="button" className="button" onClick={() => setCodeFor(null)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault();
            sendCode();
          }}
        >
          <label>
            {user.phone ? "New mobile number" : "Mobile number"}
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              required
              placeholder="0712 345 678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
            <small>We'll text a code to this number to confirm it's yours.</small>
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {message && <p role="status">{message}</p>}
          <div className="dialog-actions start">
            <button type="submit" className="button primary" disabled={busy}>
              Send code
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function EmailForm() {
  const { auth } = useApp();
  const { user } = auth;
  const [email, setEmail] = useState(user.email ?? "");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (user.is_admin) {
    return (
      <section className="card">
        <h2>Email</h2>
        <p>{user.email}</p>
        <p className="hint">The admin email and password are set in the .env file.</p>
      </section>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await auth.setEmail(email);
      setMessage(email.trim() ? "Saved." : "Email removed.");
    } catch (failure) {
      if (failure.status !== 401) {
        setError(Array.isArray(failure.detail) ? "Enter a valid email address, or leave it empty." : errorText(failure));
      }
    }
    setBusy(false);
  };

  return (
    <section className="card">
      <h2>Email (optional)</h2>
      <form className="form" onSubmit={submit}>
        <label>
          Email
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <small>Needed only if you want some alerts by email too. Leave empty to remove it.</small>
        </label>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {message && <p role="status">{message}</p>}
        <div className="dialog-actions start">
          <button type="submit" className="button primary" disabled={busy}>
            Save email
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
      <PhoneForm />
      <EmailForm />
      <HomeForm />
      <PasswordForm />
    </div>
  );
}
