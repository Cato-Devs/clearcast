export default function AlertFeed({ alerts }) {
  return (
    <div style={{ border: "1px solid #ccc", padding: 12, minWidth: 260 }}>
      <h3>Recent alerts</h3>
      {alerts.length === 0 && <p>No alerts</p>}
      {alerts.map((a) => (
        <p key={a.id}>
          <b>[{a.severity}]</b> {a.message}
          <br />
          <small>{new Date(a.created_at).toLocaleString()}</small>
        </p>
      ))}
    </div>
  );
}