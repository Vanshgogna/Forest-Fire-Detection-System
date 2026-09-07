import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="not-found">
      <h1>Page not found</h1>
      <p>The requested FireSight AI module does not exist.</p>
      <Link className="button primary" to="/dashboard">Return to Dashboard</Link>
    </main>
  );
}
