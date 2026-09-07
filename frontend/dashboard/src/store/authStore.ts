import { create } from 'zustand';
import { User } from '../types';
import { api } from '../services/api';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User | null) => void;
  loadFromStorage: () => void;
}

const safeStorage = {
  getItem: (key: string): string | null => {
    try {
      return typeof window !== 'undefined' ? window.localStorage.getItem(key) : null;
    } catch {
      return null;
    }
  },
  setItem: (key: string, value: string): void => {
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(key, value);
      }
    } catch {
      // Storage restricted in current context
    }
  },
  removeItem: (key: string): void => {
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(key);
      }
    } catch {
      // ignore
    }
  }
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  
  login: async (email, password) => {
    try {
      const response = await api.auth.login(email, password);
      const data = response.data;
      const token = data.token || data.access_token;
      const user = data.user || null;
      
      if (token) {
        safeStorage.setItem('token', token);
      }
      
      set({ user, token, isAuthenticated: true });
    } catch (error) {
      safeStorage.removeItem('token');
      set({ user: null, token: null, isAuthenticated: false });
      throw error;
    }
  },

  logout: () => {
    safeStorage.removeItem('token');
    set({ user: null, token: null, isAuthenticated: false });
  },

  setUser: (user) => {
    set({ user, isAuthenticated: !!user });
  },

  loadFromStorage: () => {
    const token = safeStorage.getItem('token');
    if (token) {
      set({
        token,
        isAuthenticated: true,
        user: null,
      });
      api.auth.getMe().then(res => {
        if (res.data) set({ user: res.data });
      }).catch(() => {
        safeStorage.removeItem('token');
        set({ token: null, isAuthenticated: false, user: null });
      });
    }
  }
}));
