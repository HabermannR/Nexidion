import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  
  // Wenn nicht authentifiziert, zu Login weiterleiten
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  
  // Wenn authentifiziert, Kinder-Komponenten rendern
  return children;
}

export default ProtectedRoute;