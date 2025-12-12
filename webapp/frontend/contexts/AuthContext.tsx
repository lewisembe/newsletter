'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi, userApi } from '@/lib/api-client';
import { useRouter } from 'next/navigation';

interface User {
  id: number;
  nombre: string;
  email: string;
  role: 'admin' | 'user' | 'enterprise';
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (nombre: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (updates: {
    nombre?: string;
    current_password?: string;
    new_password?: string;
  }) => Promise<void>;
  deleteAccount: () => Promise<void>;
  isAdmin: boolean;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Load user on mount (check if token cookie exists and is valid)
  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      const response = await authApi.getMe();
      setUser(response.data);
    } catch (error) {
      // Token invalid/expired or not logged in
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string, rememberMe: boolean = true) => {
    try {
      console.log('[AuthContext] Starting login with rememberMe:', rememberMe);
      await authApi.login(email, password, rememberMe);
      console.log('[AuthContext] Login successful, fetching user data...');

      // After login, fetch user data
      const response = await authApi.getMe();
      console.log('[AuthContext] User data fetched:', response.data);
      setUser(response.data);

      console.log('[AuthContext] Redirecting to dashboard...');
      router.push('/dashboard');
    } catch (error) {
      console.error('[AuthContext] Login error:', error);
      throw error;
    }
  };

  const register = async (nombre: string, email: string, password: string) => {
    // Register endpoint auto-logs in (sets cookie)
    const response = await authApi.register(nombre, email, password);
    setUser(response.data);
    router.push('/dashboard');
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      // Ignore logout errors
    } finally {
      setUser(null);
      router.push('/');
    }
  };

  const updateProfile = async (updates: {
    nombre?: string;
    current_password?: string;
    new_password?: string;
  }) => {
    const response = await userApi.updateProfile(updates);
    setUser(response.data);
  };

  const deleteAccount = async () => {
    try {
      await userApi.deleteProfile();
      try {
        await authApi.logout();
      } catch (error) {
        console.warn('[AuthContext] Logout after delete failed (non-fatal):', error);
      }
      setUser(null);
      router.push('/');
    } catch (error) {
      console.error('[AuthContext] Delete account error:', error);
      throw error;
    }
  };

  const refreshUser = async () => {
    try {
      const response = await authApi.getMe();
      setUser(response.data);
    } catch (error) {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        updateProfile,
        deleteAccount,
        isAdmin: user?.role === 'admin',
        refreshUser,
      }}
    >
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
