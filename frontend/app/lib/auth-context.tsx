"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, UserOut } from "./api";

interface AuthContextValue {
  // Kept for backward compatibility with existing call sites (api.getSession(token, ...)
  // etc.) — in cookie-auth mode this is often null, which is fine: the httpOnly
  // cookie (sent automatically via credentials:'include' on every request) is what
  // actually authenticates the request. Gate UI logic on `user`, not `token`.
  token: string | null;
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, accountType: "student" | "professional") => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // No token in localStorage to read anymore (see module docstring) — the httpOnly
    // cookie set by a previous login is what re-establishes the session here, if any.
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.access_token); // kept in memory for this tab only, never persisted
    setUser(res.user);
  };

  const register = async (
    email: string, password: string, fullName: string, accountType: "student" | "professional",
  ) => {
    const res = await api.register(email, password, fullName, accountType);
    setToken(res.access_token);
    setUser(res.user);
  };

  const logout = () => {
    api.logout().catch(() => {}); // clears the httpOnly cookie server-side
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
