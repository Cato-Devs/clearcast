import { useCallback, useEffect, useRef, useState } from "react";

const POLL_MS = 60 * 1000; // a backstop, in case the live connection is down
const RECONNECT_MS = 5 * 1000;
const TOAST_MS = 8 * 1000;

function merge(existing, incoming) {
  const byId = new Map(existing.map((n) => [n.id, n]));
  incoming.forEach((n) => byId.set(n.id, n));
  return [...byId.values()].sort((a, b) => b.id - a.id);
}

/** The logged-in user's notifications, updated live. */
export function useNotifications(token, request) {
  const [notifications, setNotifications] = useState([]);
  const [toasts, setToasts] = useState([]);
  const requestRef = useRef(request);
  requestRef.current = request;

  useEffect(() => {
    if (!token) {
      setNotifications([]);
      setToasts([]);
      return undefined;
    }
    let active = true;
    let socket;
    let reconnect;

    const load = () =>
      requestRef
        .current("/api/notifications")
        .then((rows) => active && setNotifications((old) => merge(old, rows)))
        .catch(() => {}); // the page keeps working, and the next check tries again
    load();
    const poll = setInterval(load, POLL_MS);

    const connect = () => {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${window.location.host}/api/ws`);
      socket.onopen = () => socket.send(token); // sent as a message, to keep it out of server logs
      socket.onmessage = (message) => {
        const notification = JSON.parse(message.data);
        setNotifications((old) => merge(old, [notification]));
        setToasts((old) => [...old, notification]);
        setTimeout(() => setToasts((old) => old.filter((t) => t.id !== notification.id)), TOAST_MS);
      };
      socket.onclose = () => {
        if (active) reconnect = setTimeout(connect, RECONNECT_MS);
      };
    };
    connect();

    return () => {
      active = false;
      clearInterval(poll);
      clearTimeout(reconnect);
      socket?.close();
    };
  }, [token]);

  const markAllRead = useCallback(async () => {
    await requestRef.current("/api/notifications/read", { method: "POST", body: {} });
    setNotifications((old) => old.map((n) => ({ ...n, read: true })));
  }, []);

  const dismissToast = useCallback((id) => setToasts((old) => old.filter((t) => t.id !== id)), []);

  return { notifications, unread: notifications.filter((n) => !n.read).length, toasts, markAllRead, dismissToast };
}
