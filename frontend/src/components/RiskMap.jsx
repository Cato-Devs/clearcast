import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const COLORS = {
  normal: "green",
  heavy_rainfall: "orange",
  flood_risk: "red",
  storm: "purple",
  extreme_temperature: "darkred",
};

export default function RiskMap({ locations }) {
  return (
    <MapContainer center={[0.0, 37.9]} zoom={6} style={{ height: 400, width: "100%" }}>
      <TileLayer
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
      />
      {locations.map((l) => (
        <CircleMarker
          key={l.id}
          center={[l.latitude, l.longitude]}
          radius={14}
          pathOptions={{ color: COLORS[l.risk_label] || "gray", fillOpacity: 0.6 }}
        >
          <Popup>
            {l.name}: {l.risk_label ? l.risk_label.replaceAll("_", " ") : "no prediction"}
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}