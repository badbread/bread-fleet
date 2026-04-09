import React from "react";

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "2rem", fontFamily: "monospace", maxWidth: 600, margin: "0 auto" }}>
          <h1 style={{ color: "#E03E3E", fontSize: 18 }}>Something went wrong</h1>
          <pre style={{ marginTop: 12, fontSize: 13, whiteSpace: "pre-wrap", color: "#37352F" }}>
            {this.state.error.message}
          </pre>
          <pre style={{ marginTop: 8, fontSize: 11, color: "#787774", whiteSpace: "pre-wrap" }}>
            {this.state.error.stack}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop: 16, padding: "6px 16px", cursor: "pointer" }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
