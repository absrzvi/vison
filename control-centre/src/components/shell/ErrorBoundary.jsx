import { Component } from 'react';
import './ErrorBoundary.css';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary">
          <div className="error-boundary__icon">!</div>
          <h2 className="error-boundary__title">Something went wrong</h2>
          <p className="error-boundary__msg">{this.state.error?.message ?? 'An unexpected error occurred.'}</p>
          <button className="btn btn--secondary" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
