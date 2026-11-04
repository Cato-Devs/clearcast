import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { useApp } from "./AppContext.jsx";
import AuthDialog from "./AuthDialog.jsx";
import { formatEat } from "./weather.js";

function AccountMenu() {
  const { auth } = useApp();
  const [open, setOpen] = useState(false);
  const menu = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (e.type === "keydown" ? e.key === "Escape" : !menu.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("click", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div className="account-menu" ref={menu}>
      <button type="button" className="button account-button" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="account-email">{auth.user.email}</span>
        <span aria-hidden="true"> ▾</span>
      </button>
      {open && (
        <div className="dropdown">
          <Link to="/account" onClick={() => setOpen(false)}>
            Account settings
          </Link>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              auth.logout();
            }}
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}

function Toasts() {
  const { notifications } = useApp();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {notifications.toasts.map((toast) => (
        <div key={toast.id} className="toast">
          <strong>{toast.title}</strong>
          <span>{toast.body}</span>
          <button
            type="button"
            className="link small"
            aria-label={`Dismiss: ${toast.title}`}
            onClick={() => notifications.dismissToast(toast.id)}
          >
            Dismiss
          </button>
        </div>
      ))}
    </div>
  );
}

export default function Layout() {
  const { auth, weather, notifications, authMode, setAuthMode } = useApp();
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => setMenuOpen(false), [pathname]);

  const links = [
    { to: "/", label: "Map" },
    { to: "/locations", label: "Locations" },
    { to: "/alerts", label: "My Alerts" },
    { to: "/about", label: "About" },
    ...(auth.user?.is_admin ? [{ to: "/admin", label: "Admin" }] : []),
  ];

  return (
    <div className="page">
      <header className="top-bar">
        <Link to="/" className="brand">
          ClearCast
        </Link>

        <button
          type="button"
          className="button menu-button"
          aria-expanded={menuOpen}
          aria-controls="main-menu"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          Menu
        </button>

        <nav id="main-menu" aria-label="Main" className={menuOpen ? "open" : undefined}>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === "/"}>
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="account">
          {auth.user ? (
            <>
              <Link
                to="/alerts#notifications"
                className="button bell"
                aria-label={`Notifications: ${notifications.unread} unread`}
              >
                Notifications
                {notifications.unread > 0 && <span className="count">{notifications.unread}</span>}
              </Link>
              <AccountMenu />
            </>
          ) : (
            <>
              <button type="button" className="button" onClick={() => setAuthMode("login")}>
                Log in
              </button>
              <button type="button" className="button primary" onClick={() => setAuthMode("register")}>
                Sign up
              </button>
            </>
          )}
        </div>
      </header>

      {auth.sessionEnded && (
        <p className="notice" role="status">
          Your login has expired. Log in again to use your account.
        </p>
      )}

      {weather.failed && (
        <p className="notice error" role="alert">
          Couldn't reach the ClearCast server.{" "}
          {weather.runList ? "Showing the last data received." : "Trying again shortly."}
        </p>
      )}

      <main>
        <Outlet />
      </main>

      <footer>
        {weather.latestIssue ? `Weather data to ${formatEat(weather.latestIssue)} EAT` : "Waiting for weather data"}
      </footer>

      <Toasts />

      {authMode && (
        <AuthDialog
          mode={authMode}
          onModeChange={setAuthMode}
          onClose={() => setAuthMode(null)}
          auth={auth}
          nairobiNames={weather.nairobiNames}
          townNames={weather.townNames}
        />
      )}
    </div>
  );
}
