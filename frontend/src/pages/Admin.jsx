import { useEffect, useState } from "react";
import api from "../api/client";

export default function Admin() {
  const [users, setUsers] = useState([]);
  const [thresholds, setThresholds] = useState([]);
  const [sources, setSources] = useState([]);
  const [model, setModel] = useState(null);
  const [msg, setMsg] = useState("");

  const load = () => {
    api.get("/admin/users").then((r) => setUsers(r.data));
    api.get("/admin/thresholds").then((r) => setThresholds(r.data));
    api.get("/admin/sources").then((r) => setSources(r.data));
    api.get("/admin/model").then((r) => setModel(r.data)).catch(() => setModel(null));
  };

  useEffect(() => { load(); }, []);

  const setRole = (id, role) => api.put(`/admin/users/${id}/role`, { role }).then(load);

  const editT = (id, k, v) =>
    setThresholds(thresholds.map((t) => (t.id === id ? { ...t, [k]: v } : t)));

  const saveT = (t) =>
    api.put(`/admin/thresholds/${t.id}`, {
      min_confidence: Number(t.min_confidence),
      severity: t.severity,
    }).then(load);

  const registerModel = async () => {
    try {
      const { data } = await api.post("/admin/model/register");
      setMsg(data.message);
      load();
    } catch {
      setMsg("ML service unavailable");
    }
  };

  return (
    <div style={{ padding: 16, display: "grid", gap: 24 }}>
      <section>
        <h3>Users</h3>
        <table>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>
                  <select value={u.role} onChange={(e) => setRole(u.id, e.target.value)}>
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3>Alert thresholds</h3>
        <table>
          <tbody>
            {thresholds.map((t) => (
              <tr key={t.id}>
                <td>{t.risk_label}</td>
                <td>
                  <input type="number" step="0.05" min="0" max="1" value={t.min_confidence}
                    onChange={(e) => editT(t.id, "min_confidence", e.target.value)} />
                </td>
                <td>
                  <select value={t.severity} onChange={(e) => editT(t.id, "severity", e.target.value)}>
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </td>
                <td><button onClick={() => saveT(t)}>Save</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3>Data sources</h3>
        <table>
          <thead>
            <tr><th>Name</th><th>Type</th><th>Status</th><th>Last fetch</th></tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.source_type}</td>
                <td>{s.is_healthy ? "healthy" : "failing"}</td>
                <td>{s.last_fetch_at ? new Date(s.last_fetch_at).toLocaleString() : "never"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3>Model</h3>
        {model ? <pre>{JSON.stringify(model, null, 2)}</pre> : <p>ML service unavailable</p>}
        <button onClick={registerModel}>Register current model version</button>
        {msg && <p>{msg}</p>}
      </section>
    </div>
  );
}