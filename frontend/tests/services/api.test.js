import { describe, it, expect, vi, beforeEach } from 'vitest';
import api, { getErrorMessage } from '../../src/services/api';

describe('API Service', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });
  });

  describe('Request Interceptor', () => {
    it('attaches Authorization header if token exists', async () => {
      localStorage.getItem.mockReturnValue('test-token');
      
      const config = { headers: {} };
      
      // The interceptors are functions in the internal array, but we can't call them directly easily
      // Instead, we can mock axios itself, or just test the exported `api` config behavior by triggering a request and intercepting it with MSW/moxios.
      // For this test, we can directly invoke the request interceptor function from the axios instance:
      const interceptor = api.interceptors.request.handlers[0].fulfilled;
      const result = await interceptor(config);
      
      expect(result.headers.Authorization).toBe('Bearer test-token');
      expect(localStorage.getItem).toHaveBeenCalledWith('codemigration_token');
    });

    it('does not attach Authorization header if token is missing', async () => {
      localStorage.getItem.mockReturnValue(null);
      
      const config = { headers: {} };
      const interceptor = api.interceptors.request.handlers[0].fulfilled;
      const result = await interceptor(config);
      
      expect(result.headers.Authorization).toBeUndefined();
    });
  });

  describe('getErrorMessage utility', () => {
    it('handles network timeouts', () => {
      expect(getErrorMessage({ code: 'ECONNABORTED' })).toContain('timed out');
    });

    it('handles 400 Bad Request', () => {
      const error = { response: { status: 400, data: { detail: 'Missing field' } } };
      expect(getErrorMessage(error)).toBe('Validation error: Missing field');
    });

    it('handles 401 Unauthorized', () => {
      const error = { response: { status: 401 } };
      expect(getErrorMessage(error)).toBe('Authentication required. Please log in again.');
    });

    it('handles 422 Unprocessable Entity with FastAPI detail array', () => {
      const error = {
        response: {
          status: 422,
          data: {
            detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address' }]
          }
        }
      };
      expect(getErrorMessage(error)).toBe('Validation error on "email": value is not a valid email address');
    });

    it('handles 500 Internal Server Error', () => {
      const error = { response: { status: 500 } };
      expect(getErrorMessage(error)).toContain('server error occurred');
    });
  });

  describe('URL Normalization & Helpers', () => {
    it('normalizes URLs without protocol by prepending https://', async () => {
      const { normalizeBackendUrl } = await import('../../src/services/api');
      expect(normalizeBackendUrl('code-migration-ai.onrender.com')).toBe('https://code-migration-ai.onrender.com');
      expect(normalizeBackendUrl('api.example.com/api/v1')).toBe('https://api.example.com/api/v1');
    });

    it('handles localhost URLs with http://', async () => {
      const { normalizeBackendUrl } = await import('../../src/services/api');
      expect(normalizeBackendUrl('localhost:8000')).toBe('http://localhost:8000');
      expect(normalizeBackendUrl('127.0.0.1:8000')).toBe('http://localhost:8000'.replace('localhost', '127.0.0.1'));
    });

    it('strips surrounding quotes and trailing slashes', async () => {
      const { normalizeBackendUrl } = await import('../../src/services/api');
      expect(normalizeBackendUrl('"https://code-migration-ai.onrender.com/"')).toBe('https://code-migration-ai.onrender.com');
      expect(normalizeBackendUrl("'https://api.domain.com///'")).toBe('https://api.domain.com');
    });

    it('preserves relative paths starting with /', async () => {
      const { normalizeBackendUrl } = await import('../../src/services/api');
      expect(normalizeBackendUrl('/api/v1')).toBe('/api/v1');
    });

    it('safely rejects placeholder and invalid URLs containing brackets or illegal characters', async () => {
      const { normalizeBackendUrl } = await import('../../src/services/api');
      expect(normalizeBackendUrl('[SENSITIVE]')).toBe('');
      expect(normalizeBackendUrl('https://[SENSITIVE]/api/v1')).toBe('');
      expect(normalizeBackendUrl('<YOUR_BACKEND_URL>')).toBe('');
    });

    it('generates correct WebSocket URL', async () => {
      const { getWebSocketUrl } = await import('../../src/services/api');
      const wsUrl = getWebSocketUrl('test-wf-123', '?token=abc');
      expect(wsUrl).toMatch(/wss?:\/\/.*\/ws\/workflows\/test-wf-123\?token=abc/);
    });
  });
});
