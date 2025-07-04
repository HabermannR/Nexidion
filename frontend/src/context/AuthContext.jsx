import React, { createContext, useContext, useState, useEffect } from 'react';
// VAULT-FIX: Importiere den useAppContext, um auf seine Funktionen zugreifen zu können
import { useAppContext } from './AppContext'; 

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Dein bestehender State ist perfekt, keine Änderungen hier
  const [token, setToken] = useState(localStorage.getItem('token'));
  
  // VAULT-FIX: Hole die fetchVaults-Funktion aus dem AppContext
  const { fetchVaults } = useAppContext();

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      // VAULT-FIX: Wenn die Seite neu geladen wird und ein Token vorhanden ist,
      // lade sofort die Vaults.
      fetchVaults();
    } else {
      localStorage.removeItem('token');
    }
    // VAULT-FIX: fetchVaults zur Abhängigkeitsliste hinzufügen.
    // Da fetchVaults mit useCallback erstellt wurde, ändert es sich nicht
    // und verursacht keine unnötigen Re-Renders.
  }, [token, fetchVaults]);

  const login = (newToken) => {
    // Diese Funktion löst den obigen useEffect aus, der dann fetchVaults aufruft.
    // Wir müssen fetchVaults hier nicht erneut aufrufen.
    setToken(newToken);
  };

  const logout = () => {
    setToken(null);
  };

  const isAuthenticated = !!token;
  const isAdmin = false;

  const value = {
    token,
    isAuthenticated,
    isLoggedIn: isAuthenticated,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  return useContext(AuthContext);
};