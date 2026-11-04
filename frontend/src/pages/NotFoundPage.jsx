import { Link } from "react-router";

export default function NotFoundPage({ title = "Page not found" }) {
  return (
    <section className="card prompt">
      <h1>{title}</h1>
      <p>
        <Link className="link" to="/">
          Go to the map
        </Link>
      </p>
    </section>
  );
}
