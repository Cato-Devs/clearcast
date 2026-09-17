const COLORS = {
  normal: "green",
  heavy_rainfall: "orange",
  flood_risk: "red",
  storm: "purple",
  extreme_temperature: "darkred",
};

const pretty = (label) => label.replaceAll("_", " ");

export default function RiskIndicator({ data }) {
  if (!data?.risk_label) {
    return <div style={{ border: "1px solid #ccc", padding: 12 }}>No prediction yet</div>;
  }
  return (
    <div style={{ border: `3px solid ${COLORS[data.risk_label] || "gray"}`, padding: 12, minWidth: 220 }}>
      <h3>Predicted risk (next 6 h)</h3>
      <p style={{ fontSize: 24, color: COLORS[data.risk_label] || "gray" }}>{pretty(data.risk_label)}</p>
      <p>Confidence: {Math.round(data.confidence * 100)}%</p>
      {data.outlook?.length > 1 && (
        <>
          <h4>Outlook</h4>
          <ul>
            {data.outlook.slice(1).map((o) => (
              <li key={o.lead_hours}>
                +{o.lead_hours} to +{o.lead_hours + 6} h: {pretty(o.risk_label)} ({Math.round(o.confidence * 100)}%)
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}