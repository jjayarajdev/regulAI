// ErrorBoundary — a screen crash must never blank the whole app. Three
// data-shape crashes in one week (zero-KPI fixtures, stale bundles, null
// seal metadata) all presented as a white page because nothing caught the
// render error. This renders the failure as a card instead: which screen,
// what threw, and how to recover. Keyed remount via `resetKey` lets
// navigation to another screen clear the error automatically.
import { Component, type ReactNode } from 'react';

interface Props { screen: string; children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    // Navigating to a different screen resets the boundary.
    if (prev.screen !== this.props.screen && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div style={{ maxWidth: 680, margin: '40px auto', border: '1px solid var(--color-divider)', padding: '26px 30px' }}>
        <div className="k" style={{ marginBottom: 6 }}>screen error · {this.props.screen}</div>
        <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 19, marginBottom: 10 }}>
          This screen hit a rendering error
        </div>
        <div className="mono" style={{
          fontSize: 11.5, lineHeight: 1.7, padding: '10px 12px', marginBottom: 14,
          background: 'color-mix(in srgb,var(--color-text) 5%,transparent)',
          whiteSpace: 'pre-wrap', overflowWrap: 'anywhere',
        }}>
          {error.message || String(error)}
        </div>
        <div style={{ fontSize: 12.5, lineHeight: 1.6, marginBottom: 14, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>
          The rest of the app is unaffected — switch screens from the sidebar, or retry this one.
          If it persists, the message above is the bug report.
        </div>
        <button className="btn btn-primary" onClick={() => this.setState({ error: null })}>
          Retry this screen
        </button>
      </div>
    );
  }
}
