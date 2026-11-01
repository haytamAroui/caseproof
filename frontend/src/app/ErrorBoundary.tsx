import { Component } from 'react';
import type { ReactNode } from 'react';
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main>
        <h1>The workspace could not open</h1>
        <p>Reload the application to start a new session.</p>
        <a href="/workspace/">Reload workspace</a>
      </main>
    ) : (
      this.props.children
    );
  }
}
