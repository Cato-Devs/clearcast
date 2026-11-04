import L from "leaflet";
import { useMemo } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import { displayBand, EVENTS } from "./weather.js";

function tooltipContent(name, eventLabel, bandLabel) {
  const element = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = name;
  element.append(title, document.createElement("br"), `${eventLabel}: ${bandLabel}`);
  return element;
}

export default function NairobiMap({ boundaries, runs, event, selected, onSelect }) {
  const bounds = useMemo(() => L.geoJSON(boundaries).getBounds(), [boundaries]);
  const eventLabel = EVENTS.find((e) => e.id === event).label;

  // Leaflet can't update these options on existing shapes, so a new key redraws them.
  const drawKey = JSON.stringify([event, selected, runs]);

  return (
    <MapContainer bounds={bounds} zoomSnap={0.25} scrollWheelZoom={false} className="leaflet-host">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors. Boundaries: geoBoundaries (IEBC, OCHA)'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <GeoJSON
        key={drawKey}
        data={boundaries}
        style={(feature) => {
          const name = feature.properties.name;
          const band = displayBand(runs[name], event);
          return { className: `region band-${band.id}${name === selected ? " selected" : ""}` };
        }}
        onEachFeature={(feature, layer) => {
          const name = feature.properties.name;
          layer.bindTooltip(tooltipContent(name, eventLabel, displayBand(runs[name], event).label), { sticky: true });
          layer.on("click", () => onSelect(name));
        }}
      />
    </MapContainer>
  );
}
