import { create } from 'zustand';

export const useAuthStore = create((set) => ({
  user: JSON.parse(localStorage.getItem('codemigration_user') || 'null'),
  token: localStorage.getItem('codemigration_token') || null,
  isAuthenticated: !!localStorage.getItem('codemigration_token'),

  setAuth: (user, token, refreshToken) => {
    localStorage.setItem('codemigration_token', token);
    if (refreshToken) {
      localStorage.setItem('codemigration_refresh_token', refreshToken);
    }
    localStorage.setItem('codemigration_user', JSON.stringify(user));
    set({ user, token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('codemigration_token');
    localStorage.removeItem('codemigration_refresh_token');
    localStorage.removeItem('codemigration_user');
    set({ user: null, token: null, isAuthenticated: false });
  },
}));
