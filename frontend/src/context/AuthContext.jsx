// src/context/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  // NEU: Ein Lade-Status für die initiale Auth-Prüfung
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  useEffect(() => {
    try {
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        setToken(storedToken);
      }
    } catch (error) {
      console.error("Failed to read token from localStorage", error);
    } finally {
      // Egal was passiert, die initiale Prüfung ist jetzt abgeschlossen
      setIsLoadingAuth(false);
    }
  }, []); // Läuft nur einmal beim App-Start

  const login = (newToken) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    localStorage.removeItem('activeVaultId');
    sessionStorage.clear();
  };

  const isAuthenticated = !!token;

  const value = {
    token,
    isAuthenticated,
    isLoggedIn: isAuthenticated,
    isLoadingAuth, // <--- Den neuen Status exportieren
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  return useContext(AuthContext);
};