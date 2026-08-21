import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAuthStore } from '../../src/stores/authStore';

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] || null),
    setItem: vi.fn((key, value) => {
      store[key] = value.toString();
    }),
    removeItem: vi.fn((key) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

describe('authStore', () => {
  beforeEach(() => {
    localStorageMock.clear();
    // Reset Zustand store state before each test
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  });

  it('has default initial state', () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  it('updates state and localStorage on setAuth', () => {
    const mockUser = { id: 1, name: 'Test User' };
    const mockToken = 'mock-token';
    const mockRefreshToken = 'mock-refresh-token';

    useAuthStore.getState().setAuth(mockUser, mockToken, mockRefreshToken);

    const state = useAuthStore.getState();
    expect(state.user).toEqual(mockUser);
    expect(state.token).toBe(mockToken);
    expect(state.isAuthenticated).toBe(true);

    expect(localStorageMock.setItem).toHaveBeenCalledWith('codemigration_token', mockToken);
    expect(localStorageMock.setItem).toHaveBeenCalledWith('codemigration_refresh_token', mockRefreshToken);
    expect(localStorageMock.setItem).toHaveBeenCalledWith('codemigration_user', JSON.stringify(mockUser));
  });

  it('clears state and localStorage on logout', () => {
    // Set initial authenticated state
    const mockUser = { id: 1, name: 'Test User' };
    const mockToken = 'mock-token';
    useAuthStore.setState({ user: mockUser, token: mockToken, isAuthenticated: true });

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
    expect(state.isAuthenticated).toBe(false);

    expect(localStorageMock.removeItem).toHaveBeenCalledWith('codemigration_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('codemigration_refresh_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('codemigration_user');
  });
});
