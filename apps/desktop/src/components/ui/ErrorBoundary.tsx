import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div
          className="flex flex-col items-center justify-center min-h-[300px] text-center p-8"
          role="alert"
        >
          <div className="p-3 rounded-full bg-rose-500/10 border border-rose-500/20 mb-4">
            <AlertTriangle className="w-8 h-8 text-rose-400" />
          </div>
          <h2 className="text-lg font-bold text-zinc-100 mb-2">Something went wrong</h2>
          <p className="text-sm text-zinc-400 font-mono mb-6 max-w-md">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <div className="flex gap-3">
            <button
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl
                         bg-cyan-glow text-black hover:bg-cyan-glow/90 transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Try Again
            </button>
            <button
              onClick={() => window.location.href = '/'}
              className="inline-flex items-center gap-2 text-xs font-semibold px-4 py-2 rounded-xl
                         bg-zinc-800 text-zinc-100 hover:bg-zinc-700 transition-all"
            >
              <Home className="w-3.5 h-3.5" />
              Go Home
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
