import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  loading: boolean;
  apiKey: string | null;
  login: (apiKey: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKey] = useState<string | null>(() => localStorage.getItem('agentwall_api_key'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  const login = (key: string) => {
    localStorage.setItem('agentwall_api_key', key);
    setApiKey(key);
  };

  const logout = () => {
    localStorage.removeItem('agentwall_api_key');
    setApiKey(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!apiKey, loading, apiKey, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}