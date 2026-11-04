import { useEffect, useRef, useState } from "react";

/** Turns an API failure into a message someone can act on. */
function errorMessage(error) {
  if (Array.isArray(error.detail)) {
    const fields = error.detail.flatMap((d) => d.loc ?? []);
    if (fields.includes("email")) return "Enter a valid email address.";
    if (fields.includes("password")) return "Passwords must be 8 to 128 characters long.";
  }
  if (error.status && typeof error.detail === "string") return error.detail;
  return "Couldn't reach the ClearCast server. Please try again.";
}

export default function AuthDialog({ mode, onModeChange, onClose, auth, nairobiNames, townNames }) {
  const dialog = useRef(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [home, setHome] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const signingUp = mode === "register";

  useEffect(() => {
    const element = dialog.current;
    element.showModal();
    return () => element.close();
  }, []);

  const changeMode = (next) => {
    setError(null);
    onModeChange(next);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (signingUp) await auth.register(email, password, home);
      else await auth.login(email, password);
      onClose();
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialog} className="auth-dialog" aria-labelledby="auth-title" onCancel={onClose}>
      <form onSubmit={submit}>
        <h2 id="auth-title">{signingUp ? "Create your account" : "Log in"}</h2>

        <label>
          Email
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label>
          Password
          <input
            type="password"
            autoComplete={signingUp ? "new-password" : "current-password"}
            required
            minLength={signingUp ? 8 : undefined}
            maxLength={128}
            aria-describedby={signingUp ? "password-hint" : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {signingUp && <small id="password-hint">At least 8 characters</small>}
        </label>

        {signingUp && (
          <label>
            Home location (optional)
            <select value={home} onChange={(e) => setHome(e.target.value)}>
              <option value="">Choose later</option>
              <optgroup label="Nairobi constituencies">
                {nairobiNames.map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </optgroup>
              <optgroup label="Other towns">
                {townNames.map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </optgroup>
            </select>
          </label>
        )}

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div className="dialog-actions">
          <button type="button" className="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="button primary" disabled={busy}>
            {signingUp ? "Sign up" : "Log in"}
          </button>
        </div>

        <p className="switch-mode">
          {signingUp ? "Already have an account? " : "New to ClearCast? "}
          <button type="button" className="link" onClick={() => changeMode(signingUp ? "login" : "register")}>
            {signingUp ? "Log in" : "Sign up"}
          </button>
        </p>
      </form>
    </dialog>
  );
}
