import { useEffect, useRef, useState } from "react";
import api from "../api/client";
import useLiveUpdates from "../hooks/useLiveUpdates";
import ConditionsPanel from "../components/ConditionsPanel";
import RiskIndicator from "../components/RiskIndicator";
import RiskMap from "../components/RiskMap";
import AlertFeed from "../components/AlertFeed";
import TrendsChart from "../components/TrendsChart";

export default function Dashboard() {
  const [locations, setLocations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [current, setCurrent] = useState(null);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const selectedRef = useRef(null);

  const loadAlerts = () => api.get("/alerts").then((r) => setAlerts(r.data));

  useEffect(() => {
    api.get("/weather/locations").then((r) => {
      setLocations(r.data);
      if (r.data.length) setSelected(r.data[0].id);
    });
    loadAlerts();
  }, []);

  useEffect(() => {
    selectedRef.current = selected;
    if (!selected) return;
    api.get(`/weather/current/${selected}`).then((r) => setCurrent(r.data)).catch(() => setCurrent(null));
    api.get(`/weather/history/${selected}?hours=48`).then((r) => setHistory(r.data));
  }, [selected]);

  useLiveUpdates((msg) => {
    if (msg.type === "update") {
      setLocations((ls) => ls.map((l) => (l.id === msg.location_id ? { ...l, ...msg.data } : l)));
      if (msg.location_id === selectedRef.current) setCurrent(msg.data);
    }
    if (msg.type === "alert") loadAlerts();
  });

  const downloadReport = async () => {
    const r = await api.get(`/reports/${selected}`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = "clearcast_report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ padding: 16, display: "grid", gap: 16 }}>
      <select value={selected ?? ""} onChange={(e) => setSelected(Number(e.target.value))}>
        {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
      </select>
      <RiskMap locations={locations} />
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <ConditionsPanel data={current} />
        <RiskIndicator data={current} />
        <AlertFeed alerts={alerts.slice(0, 5)} />
      </div>
      <TrendsChart data={history} />
      <button onClick={downloadReport} disabled={!selected}>Download prediction report (PDF)</button>
    </div>
  );
}