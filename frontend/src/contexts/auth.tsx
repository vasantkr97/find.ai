"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { apiFetch } from "@/lib/api-client";
import {
  isGoogleAuthCompleteMessage,
  openGoogleAuthPopup,
} from "@/lib/google-auth-popup";

interface AuthState {
  authenticated: boolean;
  email: string | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: () => Promise<{ ok: boolean; error?: string }>;
  logout: () => Promise<void>;
  refresh: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    authenticated: false,
    email: null,
    loading: true,
  });

  const refresh = useCallback(async () => {
    try {
      const res = await apiFetch("/api/auth/status");
      const data = await res.json();
      const authenticated = data.authenticated ?? false;
      setState({
        authenticated,
        email: data.email ?? null,
        loading: false,
      });
      return authenticated;
    } catch {
      setState({ authenticated: false, email: null, loading: false });
      return false;
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const login = useCallback(async () => {
    const popup = openGoogleAuthPopup("archon-google-auth");
    if (!popup) {
      return { ok: false, error: "Google sign-in popup was blocked. Allow pop-ups and try again." };
    }

    let pollId: number | null = null;
    let timeoutId: number | null = null;
    let settled = false;
    let handleMessage: ((event: MessageEvent) => void) | null = null;

    const resolveOnce = <T,>(resolve: (value: T) => void, value: T) => {
      if (settled) {
        return;
      }
      settled = true;
      resolve(value);
    };

    const cleanup = () => {
      if (pollId !== null) {
        window.clearInterval(pollId);
      }
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      if (handleMessage) {
        window.removeEventListener("message", handleMessage);
      }
    };

    const finishLogin = async () => {
      const authenticated = await refresh();
      if (authenticated) {
        cleanup();
        popup.close();
      }
      return authenticated;
    };

    try {
      const res = await apiFetch("/api/drive/auth");
      const data = await res.json();
      if (!data.url) {
        popup.close();
        return { ok: false, error: data.error ?? "Google sign-in is not available right now." };
      }
      popup.location.href = data.url;
      popup.focus();
    } catch {
      popup.close();
      return { ok: false, error: "Could not reach the auth server. Check that the backend is running." };
    }

    return await new Promise<{ ok: boolean; error?: string }>((resolve) => {
      handleMessage = (event: MessageEvent) => {
        if (!isGoogleAuthCompleteMessage(event)) {
          return;
        }

        void (async () => {
          if (await finishLogin()) {
            resolveOnce(resolve, { ok: true });
          }
        })();
      };

      window.addEventListener("message", handleMessage);

      pollId = window.setInterval(async () => {
        if (popup.closed) {
          cleanup();
          resolveOnce(
            resolve,
            (await refresh())
              ? { ok: true }
              : { ok: false, error: "Google sign-in was closed before it completed." }
          );
          return;
        }

        if (await finishLogin()) {
          resolveOnce(resolve, { ok: true });
        }
      }, 500);

      timeoutId = window.setTimeout(() => {
        cleanup();
        popup.close();
        resolveOnce(resolve, { ok: false, error: "Google sign-in timed out." });
      }, 60_000);
    });
  }, [refresh]);

  const logout = useCallback(async () => {
    await apiFetch("/api/auth/logout", { method: "POST" });
    setState({ authenticated: false, email: null, loading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
