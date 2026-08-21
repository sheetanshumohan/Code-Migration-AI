import React from 'react';
import { AlertTriangle, RefreshCw, WifiOff, Lock, ShieldOff, Search, Clock, Zap, Server } from 'lucide-react';

const ERROR_CONFIGS = {
  network: {
    icon: WifiOff,
    iconColor: 'text-orange-400',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/20',
  },
  401: {
    icon: Lock,
    iconColor: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/20',
  },
  403: {
    icon: ShieldOff,
    iconColor: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/20',
  },
  404: {
    icon: Search,
    iconColor: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/20',
  },
  429: {
    icon: Clock,
    iconColor: 'text-amber-400',
    bgColor: 'bg-amber-500/10',
    borderColor: 'border-amber-500/20',
  },
  timeout: {
    icon: Zap,
    iconColor: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/20',
  },
  500: {
    icon: Server,
    iconColor: 'text-red-400',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/20',
  },
  default: {
    icon: AlertTriangle,
    iconColor: 'text-red-400',
    bgColor: 'bg-red-950/10',
    borderColor: 'border-red-500/20',
  },
};

/**
 * Resolve an Axios error into a status key for ERROR_CONFIGS.
 * Can also accept a plain numeric status or the string 'network'.
 */
function resolveConfig(errorOrStatus) {
  if (!errorOrStatus) return ERROR_CONFIGS.default;

  if (typeof errorOrStatus === 'number') {
    if (errorOrStatus >= 500) return ERROR_CONFIGS[500];
    return ERROR_CONFIGS[errorOrStatus] || ERROR_CONFIGS.default;
  }

  if (typeof errorOrStatus === 'string') {
    return ERROR_CONFIGS[errorOrStatus] || ERROR_CONFIGS.default;
  }

  // Axios error object
  const err = errorOrStatus;
  if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
    return ERROR_CONFIGS.timeout;
  }
  if (!err.response) return ERROR_CONFIGS.network;
  const s = err.response.status;
  if (s >= 500) return ERROR_CONFIGS[500];
  return ERROR_CONFIGS[s] || ERROR_CONFIGS.default;
}

/**
 * ErrorState — inline error panel with icon, title, message, and optional retry.
 *
 * Props:
 *   title       {string}       — Heading text
 *   message     {string}       — Human-readable description
 *   error       {Error|number|string} — Axios error, numeric status, or 'network'
 *   onRetry     {function}     — When provided, shows a Retry button
 *   compact     {boolean}      — Smaller variant for inline use
 */
export default function ErrorState({
  title = 'Failed to load data',
  message,
  error,
  onRetry,
  compact = false,
}) {
  const config = resolveConfig(error);
  const Icon = config.icon;

  const defaultMessage = message ||
    'An unexpected error occurred while communicating with the server. Please try again.';

  if (compact) {
    return (
      <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${config.bgColor} ${config.borderColor}`}>
        <Icon className={`w-4 h-4 flex-shrink-0 ${config.iconColor}`} />
        <p className="text-xs text-gray-300 flex-1">{defaultMessage}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 text-xs font-medium transition-colors flex-shrink-0"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center rounded-2xl border ${config.bgColor} ${config.borderColor}`}>
      <div className={`w-12 h-12 rounded-full ${config.bgColor} flex items-center justify-center mb-4`}>
        <Icon className={`w-6 h-6 ${config.iconColor}`} />
      </div>
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-gray-400 max-w-md mb-6">{defaultMessage}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border font-medium text-sm transition-colors
            ${config.bgColor} hover:opacity-80 ${config.borderColor} ${config.iconColor}`}
        >
          <RefreshCw className="w-4 h-4" />
          <span>Retry Request</span>
        </button>
      )}
    </div>
  );
}
