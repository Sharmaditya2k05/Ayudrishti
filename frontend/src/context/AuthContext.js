/** Authentication and profile state, shared across the app. */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const signOut = useCallback(async () => {
    await api.setToken(null);
    setUser(null);
  }, []);

  // Restore a stored session on launch so the user is not asked to log in
  // every time the app starts.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const token = await api.loadToken();
        if (token) {
          const me = await api.getMe();
          if (!cancelled) setUser(me);
        }
      } catch (err) {
        // A stored token that no longer works is simply discarded; the user
        // lands on the login screen rather than seeing an error.
        await api.setToken(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    // Any 401 from anywhere in the app drops us back to signed-out state.
    api.onAuthError = () => {
      setUser(null);
      api.setToken(null);
    };

    return () => {
      cancelled = true;
      api.onAuthError = null;
    };
  }, []);

  const signIn = useCallback(async (email, password) => {
    setError(null);
    const result = await api.login(email, password);
    await api.setToken(result.access_token);
    setUser(result.user);
    return result.user;
  }, []);

  const register = useCallback(async (payload) => {
    setError(null);
    const result = await api.register(payload);
    await api.setToken(result.access_token);
    setUser(result.user);
    return result.user;
  }, []);

  const updateProfile = useCallback(async (payload) => {
    const updated = await api.updateMe(payload);
    setUser(updated);
    return updated;
  }, []);

  const refresh = useCallback(async () => {
    const me = await api.getMe();
    setUser(me);
    return me;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      setError,
      signIn,
      register,
      signOut,
      updateProfile,
      refresh,
      isAuthenticated: Boolean(user),
      needsOnboarding: Boolean(user) && !user.onboarded,
    }),
    [user, loading, error, signIn, register, signOut, updateProfile, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
}
