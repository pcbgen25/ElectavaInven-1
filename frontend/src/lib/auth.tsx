"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import type { Me } from "./types";

interface AuthContextType {
  user: Me | null;
  loading: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  can: (perm: string) => boolean;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    try {
      const me = await api<Me>("auth/me");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    api<Me>("auth/me")
      .then((me) => {
        if (active) setUser(me);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handleUnauth = () => {
      setUser(null);
      if (pathname !== "/login") {
        router.replace(`/login?next=${encodeURIComponent(pathname || "/dashboard")}`);
      }
    };
    window.addEventListener("electava:unauthenticated", handleUnauth);
    return () => window.removeEventListener("electava:unauthenticated", handleUnauth);
  }, [pathname, router]);

  const login = useCallback(async (email: string, password: string) => {
    const me = await api<Me>("auth/login", { method: "POST", body: { email, password } });
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api("auth/logout", { method: "POST" });
    } catch {
      // Ignore logout network/session errors
    }
    setUser(null);
    router.replace("/login");
  }, [router]);

  const permSet = useMemo(() => new Set(user?.permissions ?? []), [user]);

  const can = useCallback(
    (perm: string) => {
      if (!user) return false;
      if (user.is_super_admin) return true;
      return permSet.has(perm) || permSet.has("*");
    },
    [user, permSet],
  );

  return (
    <AuthContext.Provider value={{ user, loading, isLoading: loading, login, logout, can, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
