import { Component, type ReactNode } from "react";
import { createLogger } from "@/shared/logging/log";

const log = createLogger("error-boundary");

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    log.error(error.message, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="page state-block" role="alert">
        <h1 className="state-block__title">This page failed to render</h1>
        <p className="state-block__text">{this.state.error.message}</p>
        <p className="state-block__text">Reload the page. If it keeps failing, the source Markdown for this page may have a structure the parser does not expect.</p>
        <button type="button" className="btn btn--primary" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </div>
    );
  }
}
