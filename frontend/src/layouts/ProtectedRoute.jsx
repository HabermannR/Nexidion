// src/layouts/ProtectedRoute.jsx
import React, { useEffect } from 'react';
import { Navigate, Outlet, useNavigate } from 'react-router-dom';
import AppLoading from '../components/AppLoading';

// 1. IMPORTIERE DEINEN SHARED HOOK HIER:
import { useUserQuery } from '../features/auth/useUserQuery';

export function ProtectedRoute() {
    const { data: user, isLoading, isError } = useUserQuery();
    const navigate = useNavigate();

    useEffect(() => {
        if (!isLoading && isError) {
            console.error("Auth-Fehler erkannt, leite zum Login um.");
            localStorage.removeItem('authToken');
            navigate('/login', { replace: true });
        }
    }, [isLoading, isError, navigate]);

    const hasToken = !!localStorage.getItem('authToken');

    if (!hasToken) {
        return <Navigate to="/login" replace />;
    }

    if (isLoading) {
        return <AppLoading />;
    }

    if (user) {
        return <Outlet />;
    }

    return <AppLoading />;
}