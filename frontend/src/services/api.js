import axios from 'axios';
import toast from 'react-hot-toast';

export const defaultProductionBackend = 'https://code-migration-ai.onrender.com';

/**
 * Normalizes any backend URL string, ensuring proper protocol (https://)
 * and stripping stray quotes or trailing slashes.
 */
export function normalizeBackendUrl(input) {
  if (!input || typeof input !== 'string') return '';
  let url = input.trim();
  url = url.replace(/^['"]+|['"]+$/g, '').trim();
  if (!url) return '';

  // Reject placeholder tokens or invalid characters with brackets (e.g. [SENSITIVE], [APP], <APP>)
  if (/[[\]<>{}|\\^`]/.test(url)) {
    return '';
  }

  if (url.startsWith('/')) {
    return url.replace(/\/+$/, '');
  }

  if (!/^https?:\/\//i.test(url)) {
    if (/^(localhost|127\.0\.0\.1)(:\d+)?/i.test(url)) {
      url = `http://${url}`;
    } else {
      url = `https://${url}`;
    }
  }

  // Ensure the constructed URL is strictly valid
  try {
    const parsed = new URL(url);
    if (!parsed.hostname || parsed.hostname.includes('[') || parsed.hostname.includes(']')) {
      return '';
    }
  } catch {
    return '';
  }

  return url.replace(/\/+$/, '');
}

/**
 * Returns the root backend domain (e.g. "https://code-migration-ai.onrender.com" or "").
 */
export function getBackendBaseUrl() {
  const envUrl = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    const normalized = normalizeBackendUrl(envUrl);
    return normalized.replace(/\/api\/v1\/?$/, '').replace(/\/+$/, '');
  }

  return defaultProductionBackend;
}

/**
 * Returns the fully-qualified or relative API base URL (ending with "/api/v1").
 */
export function getApiBaseUrl() {
  const root = getBackendBaseUrl();
  return `${root}/api/v1`;
}

/**
 * Returns the absolute or relative Google OAuth initialization URL.
 */
export function getGoogleLoginUrl() {
  const root = getBackendBaseUrl();
  return `${root}/api/v1/auth/google/login`;
}

/**
 * Resolves the WebSocket URL for live workflow events.
 */
export function getWebSocketUrl(activeWorkflowId, tokenQuery = '') {
  const root = getBackendBaseUrl();
  const wsBase = root.replace(/^http/, 'ws');
  return `${wsBase}/ws/workflows/${activeWorkflowId}${tokenQuery}`;
}

const api = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 s global timeout
});

// ─────────────────────────────────────────────────────────────────────────────
// Request Interceptor: Attach JWT Bearer Token
// ─────────────────────────────────────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('codemigration_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─────────────────────────────────────────────────────────────────────────────
// Token refresh state
// ─────────────────────────────────────────────────────────────────────────────
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

/**
 * Extract a human-readable message from an Axios error.
 * This is the single source of truth for error-to-string translation.
 * It is exported so components can use it independently if needed.
 */
export function getErrorMessage(error) {
  // ── Network / timeout ──────────────────────────────────────────────────────
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return 'Request timed out. The server is taking too long to respond. Please retry.';
  }
  if (!error.response) {
    return 'Network error. Please check your internet connection and try again.';
  }

  const status = error.response?.status;
  const data   = error.response?.data;

  // Backend may return `detail` (FastAPI default), `message`, or a string body.
  const backendDetail =
    (typeof data === 'string' ? data : null) ||
    data?.detail ||
    data?.message ||
    null;

  // ── Status-specific ────────────────────────────────────────────────────────
  switch (status) {
    case 400:
      return backendDetail
        ? `Validation error: ${backendDetail}`
        : 'Invalid request. Please review the fields and try again.';

    case 401:
      return backendDetail || 'Authentication required. Please log in again.';

    case 403:
      return backendDetail || 'Access denied. You do not have permission to perform this action.';

    case 404:
      return backendDetail || 'The requested resource was not found.';

    case 409:
      return backendDetail
        ? `Conflict: ${backendDetail}`
        : 'A conflict occurred. The resource may already exist.';

    case 422: {
      // FastAPI validation errors have a `detail` array
      if (Array.isArray(data?.detail)) {
        const first = data.detail[0];
        const field = first?.loc?.slice(1).join('.') || 'field';
        return `Validation error on "${field}": ${first?.msg || 'Invalid value.'}`;
      }
      return backendDetail || 'Unprocessable request. Please check the submitted data.';
    }

    case 429: {
      const retryAfter = error.response.headers?.['retry-after'];
      if (backendDetail) return backendDetail;
      return retryAfter
        ? `Rate limit exceeded. Please wait ${retryAfter} second(s) before retrying.`
        : 'Too many requests. Please slow down and try again shortly.';
    }

    default:
      if (status >= 500) {
        return 'A server error occurred. Our engineering team has been notified. Please try again later.';
      }
      return backendDetail || 'An unexpected error occurred. Please try again.';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Response Interceptor: Global error handling
// ─────────────────────────────────────────────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // ── 401 → attempt token refresh (once) ─────────────────────────────────
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue this request until the refresh completes
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('codemigration_refresh_token');
      if (!refreshToken) {
        isRefreshing = false;
        localStorage.removeItem('codemigration_token');
        localStorage.removeItem('codemigration_refresh_token');
        localStorage.removeItem('codemigration_user');
        // Only toast+redirect once; skip global toast below via _silenced flag
        originalRequest._silenced = true;
        toast.error('Session expired. Please log in again.');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(
          `${api.defaults.baseURL}/auth/refresh`,
          { refresh_token: refreshToken },
        );
        localStorage.setItem('codemigration_token', data.access_token);
        localStorage.setItem('codemigration_refresh_token', data.refresh_token);
        api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        originalRequest.headers.Authorization    = `Bearer ${data.access_token}`;
        processQueue(null, data.access_token);
        // Retry the original request — don't show a toast for this case
        return api(originalRequest);
      } catch (err) {
        processQueue(err, null);
        localStorage.removeItem('codemigration_token');
        localStorage.removeItem('codemigration_refresh_token');
        localStorage.removeItem('codemigration_user');
        err._silenced = true;
        toast.error('Authentication failed. Please log in again.');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }

    // ── Global toast for all other errors (unless silenced) ─────────────────
    // Requests can opt-out of the global toast by setting config._silent = true
    if (!originalRequest?._silenced && !originalRequest?._silent) {
      const message = getErrorMessage(error);
      toast.error(message, {
        duration: 6000,
        position: 'bottom-right',
        id: `api-error-${error.response?.status ?? 'network'}`, // deduplicate same-status toasts
      });
    }

    return Promise.reject(error);
  },
);

export default api;
