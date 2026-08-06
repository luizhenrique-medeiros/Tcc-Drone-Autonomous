import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { adminApi, type AdminUser, type LoginInput } from '../../services';
import { sessionToken } from '../../services/session';
import { AuthContext, type AuthContextValue } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const restore = async () => {
      if (!sessionToken.get()) {
        if (mounted) setIsLoading(false);
        return;
      }
      try {
        const currentUser = await adminApi.me();
        if (currentUser.role !== 'ADMIN') {
          sessionToken.clear();
          return;
        }
        if (mounted) setUser(currentUser);
      } catch {
        sessionToken.clear();
      } finally {
        if (mounted) setIsLoading(false);
      }
    };
    void restore();
    return () => {
      mounted = false;
    };
  }, []);

  const login = useCallback(async (input: LoginInput) => {
    const session = await adminApi.login(input);
    if (session.user.role !== 'ADMIN') {
      sessionToken.clear();
      throw new Error('Esta conta não possui acesso administrativo.');
    }
    sessionToken.set(session.access_token);
    setUser(session.user);
  }, []);

  const logout = useCallback(() => {
    sessionToken.clear();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, logout }),
    [isLoading, login, logout, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
