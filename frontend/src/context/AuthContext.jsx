import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // KEY FIX: Initialize the state by READING from localStorage.
  // If a token exists in storage, we start in a logged-in state.
  const [token, setToken] = useState(localStorage.getItem('token'));

  // This effect keeps localStorage in sync when the token changes (on login/logout)
  useEffect(() => {
    if (token) {
      // When login() is called, the new token is saved here.
      localStorage.setItem('token', token);
    } else {
      // When logout() is called, the token is removed.
      localStorage.removeItem('token');
    }
  }, [token]);

  const login = (newToken) => {
    setToken(newToken);
  };

  const logout = () => {
    setToken(null);
  };

  // 'isAuthenticated' is now correctly derived from the persistent state.
  // !! turns the token string (or null) into a true/false boolean.
  const isAuthenticated = !!token;
  const isAdmin = false; // Implement admin logic if you need it

  const value = {
    token,
    isAuthenticated, // This is for the Login component's redirect
    isLoggedIn: isAuthenticated, // This is for the TopBar (good to use consistent naming)
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => {
  return useContext(AuthContext);
};