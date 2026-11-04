import L from "leaflet";
import { useEffect, useMemo, useRef } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import { displayBand, EVENTS } from "./weather.js";

const BASE_STYLE = { className: "region" };

function tooltipContent(name, eventLabel, bandLabel) {
  const element = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = name;
  element.append(title, document.createElement("br"), `${eventLabel}: ${bandLabel}`);
  return element;
}

/** The constituency shapes. This sits inside MapContainer because the map only creates what's
    inside it once it's ready, so this effect always runs with the shapes already in place. */
function Shapes({ boundaries, runs, event, selected, onSelect }) {
  const shapes = useRef(null);

  // Updates the existing shapes. Redrawing them would close an open tooltip and could lose a click
  // that lands during the redraw.
  useEffect(() => {
    const eventLabel = EVENTS.find((e) => e.id === event).label;
    shapes.current?.eachLayer((layer) => {
      const name = layer.feature.properties.name;
      const band = displayBand(runs[name], event);
      const isSelected = name === selected;
      layer
        .getElement()
        ?.setAttribute("class", `leaflet-interactive region band-${band.id}${isSelected ? " selected" : ""}`);
      layer.setTooltipContent(tooltipContent(name, eventLabel, band.label));
      if (isSelected) layer.bringToFront(); // so its outline isn't hidden by its neighbours
    });
  }, [runs, event, selected]);

  return (
    <GeoJSON
      ref={shapes}
      data={boundaries}
      style={BASE_STYLE}
      onEachFeature={(feature, layer) => {
        layer.bindTooltip("", { sticky: true });
        layer.on("click", () => onSelect(feature.properties.name));
      }}
    />
  );
}

export default function NairobiMap({ boundaries, runs, event, selected, onSelect }) {
  const bounds = useMemo(() => L.geoJSON(boundaries).getBounds(), [boundaries]);
  return (
    <MapContainer bounds={bounds} zoomSnap={0.25} scrollWheelZoom={false} className="leaflet-host">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors. Boundaries: geoBoundaries (IEBC, OCHA)'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Shapes boundaries={boundaries} runs={runs} event={event} selected={selected} onSelect={onSelect} />
    </MapContainer>
  );
}
