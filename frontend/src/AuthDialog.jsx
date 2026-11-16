import { useEffect, useRef, useState } from "react";

/** Turns an API failure into a message someone can act on. */
function errorMessage(error) {
  if (Array.isArray(error.detail)) {
    const fields = error.detail.flatMap((d) => d.loc ?? []);
    if (fields.includes("email")) return "Enter a valid email address, or leave it empty.";
    if (fields.includes("password")) return "Passwords must be 8 to 128 characters long.";
  }
  if (error.status && typeof error.detail === "string") return error.detail;
  return "Couldn't reach the ClearCast server. Please try again.";
}

export default function AuthDialog({ mode, onModeChange, onClose, auth, nairobiNames, townNames }) {
  const dialog = useRef(null);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [loginName, setLoginName] = useState("");
  const [password, setPassword] = useState("");
  const [home, setHome] = useState("");
  const [codeFor, setCodeFor] = useState(null); // the phone number a sign-up code was sent to
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState(null);
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
    setCodeFor(null);
    onModeChange(next);
  };

  const sendCode = async () => {
    const sentTo = await auth.startRegister({ phone, email, password, homeLocation: home });
    setCodeFor(sentTo);
    setCode("");
    setNotice(`We sent a 6-digit code by SMS to ${sentTo}.`);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (!signingUp) {
        await auth.login(loginName, password);
        onClose();
      } else if (codeFor) {
        await auth.verifyRegister(codeFor, code);
        onClose();
      } else {
        await sendCode();
        setBusy(false);
      }
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(false);
    }
  };

  const resend = async () => {
    setError(null);
    setNotice(null);
    try {
      await sendCode();
    } catch (failure) {
      setError(errorMessage(failure));
    }
  };

  if (signingUp && codeFor) {
    return (
      <dialog ref={dialog} className="auth-dialog" aria-labelledby="auth-title" onCancel={onClose}>
        <form onSubmit={submit}>
          <h2 id="auth-title">Confirm your number</h2>
          {notice && <p role="status">{notice}</p>}
          <label>
            Code
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              required
              aria-describedby="code-hint"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            />
            <small id="code-hint">It expires in 10 minutes.</small>
          </label>

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <div className="dialog-actions">
            <button type="button" className="button" onClick={() => setCodeFor(null)}>
              Back
            </button>
            <button type="submit" className="button primary" disabled={busy}>
              Confirm and sign up
            </button>
          </div>

          <p className="switch-mode">
            No SMS?{" "}
            <button type="button" className="link" onClick={resend}>
              Send a new code
            </button>
          </p>
        </form>
      </dialog>
    );
  }

  return (
    <dialog ref={dialog} className="auth-dialog" aria-labelledby="auth-title" onCancel={onClose}>
      <form onSubmit={submit}>
        <h2 id="auth-title">{signingUp ? "Create your account" : "Log in"}</h2>

        {signingUp ? (
          <>
            <label>
              Mobile number
              <input
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                required
                placeholder="0712 345 678"
                aria-describedby="phone-hint"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <small id="phone-hint">
                We'll text you a code to confirm it. Your alerts are sent here, and you log in with it.
              </small>
            </label>
            <label>
              Email (optional)
              <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
          </>
        ) : (
          <label>
            Mobile number or email
            <input
              type="text"
              autoComplete="username"
              required
              value={loginName}
              onChange={(e) => setLoginName(e.target.value)}
            />
          </label>
        )}

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
            {signingUp ? "Send code" : "Log in"}
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
