import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { ChatAPI } from '../services/api';

export interface AuthUser {
  username: string;
  display_name: string;
  role: 'admin' | 'user';
  tenant_id: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<{ error?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY = 'aios_auth_token';
const USER_KEY = 'aios_auth_user';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const storedToken = localStorage.getItem(STORAGE_KEY);
    const storedUser = localStorage.getItem(USER_KEY);
    if (storedToken && storedUser) {
      try {
        const parsed = JSON.parse(storedUser) as AuthUser;
        // Validate token is still good
        ChatAPI.validateToken(storedToken)
          .then(() => {
            setToken(storedToken);
            setUser(parsed);
          })
          .catch(() => {
            // Token expired or invalid — clear
            localStorage.removeItem(STORAGE_KEY);
            localStorage.removeItem(USER_KEY);
          })
          .finally(() => setLoading(false));
      } catch {
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem(USER_KEY);
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await ChatAPI.login(username, password);
      if (res.status === 'success' && res.token) {
        const u = res.user as AuthUser;
        setToken(res.token);
        setUser(u);
        localStorage.setItem(STORAGE_KEY, res.token);
        localStorage.setItem(USER_KEY, JSON.stringify(u));
        // Set token for all future API calls
        ChatAPI.setAuthToken(res.token);
        return {};
      }
      return { error: res.detail || 'Invalid credentials' };
    } catch (e) {
      return { error: e instanceof Error ? e.message : 'Login failed' };
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(USER_KEY);
    ChatAPI.setAuthToken(null);
  }, []);

  // Sync token to API service whenever it changes
  useEffect(() => {
    if (token) {
      ChatAPI.setAuthToken(token);
    }
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
