import { useEffect, useState } from "react";
import api from "../api/client";

export default function Settings() {
  const [p, setP] = useState(null);
  const [locations, setLocations] = useState([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.get("/auth/me").then((r) => setP(r.data));
    api.get("/weather/locations").then((r) => setLocations(r.data));
  }, []);
  if (!p) return <p>Loading…</p>;

  const save = async () => {
    await api.put("/auth/preferences", {
      notify_email: p.notify_email, notify_sms: p.notify_sms, phone: p.phone || null,
      min_severity: p.min_severity, location_id: p.location_id || null,
    });
    setMsg("Saved");
  };

  return (
    <div style={{ padding: 16, display: "grid", gap: 8, maxWidth: 360 }}>
      <label><input type="checkbox" checked={p.notify_email}
        onChange={(e) => setP({ ...p, notify_email: e.target.checked })} /> Email alerts</label>
      <label><input type="checkbox" checked={p.notify_sms}
        onChange={(e) => setP({ ...p, notify_sms: e.target.checked })} /> SMS alerts</label>
      <input placeholder="Phone" value={p.phone || ""} onChange={(e) => setP({ ...p, phone: e.target.value })} />
      <select value={p.min_severity} onChange={(e) => setP({ ...p, min_severity: e.target.value })}>
        <option value="low">Low and above</option>
        <option value="medium">Medium and above</option>
        <option value="high">High only</option>
      </select>
      <select value={p.location_id ?? ""}
        onChange={(e) => setP({ ...p, location_id: e.target.value ? Number(e.target.value) : null })}>
        <option value="">All locations</option>
        {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
      </select>
      <button onClick={save}>Save</button>
      {msg && <p>{msg}</p>}
    </div>
  );
}