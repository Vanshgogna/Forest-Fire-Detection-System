import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    void error;
    void info;
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="error-state" role="alert">
          <h1>FireSight AI is recovering</h1>
          <p>The current view could not be loaded. Refresh the page or return to the dashboard.</p>
          <a className="button primary" href="/dashboard">
            Open dashboard
          </a>
        </main>
      );
    }

    return this.props.children;
  }
}
