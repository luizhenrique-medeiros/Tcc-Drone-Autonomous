import { createContext } from 'react';
import type { AdminUser, LoginInput } from '../../services';

export interface AuthContextValue {
  user: AdminUser | null;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
