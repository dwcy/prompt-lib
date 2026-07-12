// Per-module error boundary: catches render/data errors and offers a retry that remounts only
// this module's subtree (via a bumped key), keeping the rest of the shell interactive.
import { Component, Fragment, type ReactNode } from "react";

export interface ModuleErrorBoundaryProps {
  moduleTitle: string;
  children: ReactNode;
}

interface ModuleErrorBoundaryState {
  error: Error | null;
  resetKey: number;
}

// React error boundaries require a class component — there is no hook equivalent (React docs).
export class ModuleErrorBoundary extends Component<
  ModuleErrorBoundaryProps,
  ModuleErrorBoundaryState
> {
  state: ModuleErrorBoundaryState = { error: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): Pick<ModuleErrorBoundaryState, "error"> {
    return { error };
  }

  private handleRetry = (): void => {
    this.setState((current) => ({ error: null, resetKey: current.resetKey + 1 }));
  };

  render(): ReactNode {
    const { error, resetKey } = this.state;
    if (error !== null) {
      return (
        <div className="module-error-boundary select-none" role="alert">
          <p className="module-error-boundary__title">{this.props.moduleTitle} failed to load</p>
          <p className="module-error-boundary__detail">{error.message}</p>
          <button type="button" onClick={this.handleRetry}>
            Retry
          </button>
        </div>
      );
    }
    return <Fragment key={resetKey}>{this.props.children}</Fragment>;
  }
}
