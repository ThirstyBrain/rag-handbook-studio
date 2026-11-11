import { Link } from "@/shared/router/router";

export function NotFound() {
  return (
    <div className="page state-block">
      <p className="state-block__code">404</p>
      <h1 className="state-block__title">No page at this address</h1>
      <p className="state-block__text">The link may point to a chapter that has not been written yet. The contents page lists every written and planned chapter.</p>
      <div className="state-block__actions">
        <Link className="btn btn--primary" href="/handbook">
          Open contents
        </Link>
        <Link className="btn btn--quiet" href="/">
          Go to the start page
        </Link>
      </div>
    </div>
  );
}
