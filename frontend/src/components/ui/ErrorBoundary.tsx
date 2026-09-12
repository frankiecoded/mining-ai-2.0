import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' };

  static getDerivedStateFromError(error: unknown): State {
    return { hasError: true, message: error instanceof Error ? error.message : 'Something went wrong.' };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('UI error boundary:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-full flex items-center justify-center px-6">
          <div className="max-w-sm text-center">
            <p className="text-sm font-semibold text-white mb-1">This view hit a snag</p>
            <p className="text-[12px] text-zinc-500 break-words">{this.state.message}</p>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, message: '' })}
              className="mt-4 px-4 py-2 rounded-xl text-[13px] font-medium bg-white/10 hover:bg-white/15 text-white"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}