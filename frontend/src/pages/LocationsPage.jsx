import { useApp } from "../AppContext.jsx";
import { EventPicker, LocationTable } from "../components.jsx";

export default function LocationsPage() {
  const { weather } = useApp();
  return (
    <div className="stack">
      <h1 className="page-title">Locations</h1>
      <EventPicker />
      <div className="tables">
        <LocationTable title="Nairobi constituencies" locations={weather.nairobiNames} />
        <LocationTable title="Other towns" locations={weather.townNames} />
      </div>
    </div>
  );
}
