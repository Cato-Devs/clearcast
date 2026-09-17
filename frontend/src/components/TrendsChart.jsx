import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend } from "recharts";

export default function TrendsChart({ data }) {
  if (!data.length) return <p>No history yet</p>;
  const rows = data.map((d) => ({ ...d, time: new Date(d.timestamp).toLocaleString() }));
  return (
    <div>
      <h3>Last 48 hours</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={rows}>
          <XAxis dataKey="time" minTickGap={40} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line dataKey="temperature" name="Temperature (°C)" stroke="#e67e22" dot={false} />
          <Line dataKey="rainfall" name="Rainfall (mm/h)" stroke="#2980b9" dot={false} />
          <Line dataKey="humidity" name="Humidity (%)" stroke="#27ae60" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}