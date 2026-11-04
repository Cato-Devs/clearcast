import { Link, useParams } from "react-router";
import { useApp } from "../AppContext.jsx";
import { EventList, HomeControl } from "../components.jsx";
import NotFoundPage from "./NotFoundPage.jsx";

export default function LocationPage() {
  const { name } = useParams();
  const { weather } = useApp();
  const known = [...weather.nairobiNames, ...weather.townNames];

  // Wait for the list of locations before saying that one doesn't exist
  if (known.length > 0 && !known.includes(name)) return <NotFoundPage title="Location not found" />;

  return (
    <div className="stack narrow">
      <p>
        <Link className="link small" to="/locations">
          ← All locations
        </Link>
      </p>
      <section className="card detail" aria-labelledby="detail-title">
        <div className="detail-head">
          <h1 id="detail-title" className="card-title">
            {name}
          </h1>
          <HomeControl key={name} name={name} />
        </div>
        <EventList name={name} />
        <p className="card-foot">
          <Link className="link small" to={`/alerts?location=${encodeURIComponent(name)}`}>
            Create an alert for {name}
          </Link>
        </p>
      </section>
    </div>
  );
}
