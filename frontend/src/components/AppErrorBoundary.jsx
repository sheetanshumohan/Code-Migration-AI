import React from 'react';
import { AlertTriangle, RefreshCw, Home, LogIn } from 'lucide-react';

/**
 * AppErrorBoundary — catches render-time React errors anywhere in the subtree
 * and displays a safe, actionable error screen instead of a blank white page.
 *
 * Usage:
 *   <AppErrorBoundary>
 *     <ProtectedLayout />
 *   </AppErrorBoundary>
 */
export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    // In production this would call an error tracking service (Sentry, etc.)
    console.error('[AppErrorBoundary] Uncaught render error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleTryAgain = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.reload();
  };

  handleGoToDashboard = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (window.location.pathname === '/') {
      window.location.reload();
    } else {
      window.location.href = '/';
    }
  };

  handleGoToLogin = () => {
    try {
      localStorage.removeItem('codemigration_token');
      localStorage.removeItem('codemigration_user');
      localStorage.removeItem('codemigration_active_workflow_id');
    } catch (_) {}
    this.setState({ hasError: false, error: null, errorInfo: null });
    window.location.href = '/login';
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const message =
      this.state.error?.message ||
      'An unexpected rendering error occurred.';

    return (
      <div className="min-h-screen bg-[#0B0F19] flex items-center justify-center p-8">
        <div className="max-w-lg w-full text-center space-y-6">
          {/* Icon */}
          <div className="flex justify-center">
            <div className="w-20 h-20 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center">
              <AlertTriangle className="w-10 h-10 text-red-400" />
            </div>
          </div>

          {/* Heading */}
          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-white">Something Went Wrong</h1>
            <p className="text-sm text-gray-400 leading-relaxed">
              The application encountered an unexpected error. You can return to the dashboard, re-authenticate, or retry the request.
            </p>
          </div>

          {/* Error detail (collapsed in production) */}
          {import.meta.env.DEV && (
            <details className="text-left">
              <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-300 transition-colors">
                Developer Details
              </summary>
              <pre className="mt-2 p-4 rounded-xl bg-gray-900 border border-gray-800 text-xs text-red-400 overflow-auto max-h-48 whitespace-pre-wrap">
                {message}
                {this.state.errorInfo?.componentStack || ''}
              </pre>
            </details>
          )}

          {/* Actions */}
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <button
              id="error-boundary-retry"
              onClick={this.handleTryAgain}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Try Again</span>
            </button>
            <button
              id="error-boundary-home"
              onClick={this.handleGoToDashboard}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 text-xs font-semibold transition-all cursor-pointer"
            >
              <Home className="w-4 h-4 text-cyan-400" />
              <span>Go to Dashboard</span>
            </button>
            <button
              id="error-boundary-login"
              onClick={this.handleGoToLogin}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 text-xs font-semibold transition-all cursor-pointer"
            >
              <LogIn className="w-4 h-4 text-amber-400" />
              <span>Go to Login</span>
            </button>
          </div>
        </div>
      </div>
    );
  }
}
