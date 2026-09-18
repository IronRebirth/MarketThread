"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  clearStoredAccessToken,
  getCurrentUser,
  getStoredAccessToken,
  login,
  register,
  storeAccessToken,
  type LoginRequest,
  type RegisterRequest,
  type User,
} from "../../lib/auth-api";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginRequest) => Promise<User>;
  register: (payload: RegisterRequest) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearSession = useCallback(() => {
    clearStoredAccessToken();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    const accessToken = getStoredAccessToken();

    if (!accessToken) {
      setUser(null);
      return null;
    }

    try {
      const nextUser = await getCurrentUser(accessToken);

      setUser(nextUser);

      return nextUser;
    } catch {
      clearSession();
      return null;
    }
  }, [clearSession]);

  useEffect(() => {
    let isMounted = true;

    const restoreSession = async () => {
      try {
        const accessToken = getStoredAccessToken();

        if (!accessToken) {
          return;
        }

        const nextUser = await getCurrentUser(accessToken);

        if (isMounted) {
          setUser(nextUser);
        }
      } catch {
        if (isMounted) {
          clearSession();
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void restoreSession();

    return () => {
      isMounted = false;
    };
  }, [clearSession]);

  useEffect(() => {
    const handleAuthExpired = () => {
      clearSession();
    };

    window.addEventListener(
      "marketthread-auth-expired",
      handleAuthExpired,
    );

    return () => {
      window.removeEventListener(
        "marketthread-auth-expired",
        handleAuthExpired,
      );
    };
  }, [clearSession]);

  const handleLogin = useCallback(
    async (payload: LoginRequest): Promise<User> => {
      const tokenResponse = await login(payload);

      storeAccessToken(tokenResponse.access_token);

      try {
        const nextUser = await getCurrentUser(tokenResponse.access_token);

        setUser(nextUser);

        return nextUser;
      } catch (error) {
        clearSession();
        throw error;
      }
    },
    [clearSession],
  );

  const handleRegister = useCallback(
    async (payload: RegisterRequest): Promise<User> => {
      const registeredUser = await register(payload);

      return registeredUser;
    },
    [],
  );

  const handleLogout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      login: handleLogin,
      register: handleRegister,
      logout: handleLogout,
      refreshUser,
    }),
    [
      handleLogin,
      handleLogout,
      handleRegister,
      isLoading,
      refreshUser,
      user,
    ],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (context === null) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
