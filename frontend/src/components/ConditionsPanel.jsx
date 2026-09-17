export default function ConditionsPanel({ data }) {
  if (!data) return <div style={{ border: "1px solid #ccc", padding: 12 }}>No data yet</div>;
  return (
    <div style={{ border: "1px solid #ccc", padding: 12, minWidth: 220 }}>
      <h3>Current conditions</h3>
      <p>Temperature: {data.temperature ?? "-"} °C</p>
      <p>Humidity: {data.humidity ?? "-"} %</p>
      <p>Wind speed: {data.wind_speed ?? "-"} m/s</p>
      <p>Pressure: {data.pressure ?? "-"} hPa</p>
      <p>Rainfall: {data.rainfall ?? "-"} mm/h</p>
    </div>
  );
}