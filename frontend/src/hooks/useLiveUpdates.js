import { useEffect } from "react";

export default function useLiveUpdates(onMessage) {
  useEffect(() => {
    const token = localStorage.getItem("token");
    const ws = new WebSocket(`${import.meta.env.VITE_WS_URL}?token=${token}`);
    ws.onmessage = (e) => onMessage(JSON.parse(e.data));
    return () => ws.close();
  }, []);
}