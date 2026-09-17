import { useEffect, useState } from "react";
import api from "../api/client";

export default function Alerts() {
  const [alerts, setAlerts] = useState([]);
  const [type, setType] = useState("");
  const [severity, setSeverity] = useState("");

  const load = () =>
    api.get("/alerts", { params: { alert_type: type || undefined, severity: severity || undefined } })
      .then((r) => setAlerts(r.data));

  useEffect(() => { load(); }, [type, severity]);

  const ack = async (id) => { await api.post(`/alerts/${id}/acknowledge`); load(); };

  return (
    <div style={{ padding: 16 }}>
      <select value={type} onChange={(e) => setType(e.target.value)}>
        <option value="">All types</option>
        <option value="heavy_rainfall">Heavy rainfall</option>
        <option value="flood_risk">Flood risk</option>
        <option value="storm">Storm</option>
        <option value="extreme_temperature">Extreme temperature</option>
      </select>
      <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
        <option value="">All severities</option>
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
      <table>
        <thead>
          <tr><th>Time</th><th>Type</th><th>Severity</th><th>Message</th><th>Status</th></tr>
        </thead>
        <tbody>
          {alerts.map((a) => (
            <tr key={a.id}>
              <td>{new Date(a.created_at).toLocaleString()}</td>
              <td>{a.type}</td>
              <td>{a.severity}</td>
              <td>{a.message}</td>
              <td>{a.acknowledged ? "Acknowledged" : <button onClick={() => ack(a.id)}>Acknowledge</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {alerts.length === 0 && <p>No alerts</p>}
    </div>
  );
}