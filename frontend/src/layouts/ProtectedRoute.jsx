// src/layouts/ProtectedRoute.jsx (Finale, optimierte Version)

import React, { useEffect } from 'react';
import { Navigate, Outlet, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/apiClient';
import AppLoading from '../components/AppLoading';

// Der Hook bleibt fast gleich, wird aber nur aktiviert, wenn ein Token da ist.
const useUserQuery = () => {
    const token = localStorage.getItem('authToken');

    return useQuery({
        queryKey: ['user'],
        queryFn: () => apiClient.get('/api/auth/me').then(res => res.data),

        // OPTIMIERUNG: Führe die Query nur aus, wenn ein Token existiert.
        enabled: !!token,

        // Wir behalten die sinnvolle Retry-Logik bei
        retry: (failureCount, error) => {
            if (error.response?.status === 401 || error.response?.status === 404) {
                return false; // Bei Auth-Fehlern nicht wiederholen.
            }
            return failureCount < 1;
        },
    });
}

export function ProtectedRoute() {
    const { data: user, isLoading, isError } = useUserQuery();
    const navigate = useNavigate(); // useNavigate für den reaktiven Redirect

    // ROBUSTHEITS-VERBESSERUNG: Reagiert auf Fehler im laufenden Betrieb.
    // Wenn der Token abläuft, während die App offen ist, wird der User ausgeloggt.
    useEffect(() => {
        if (!isLoading && isError) {
            console.error("Auth-Fehler erkannt, leite zum Login um.");
            localStorage.removeItem('authToken'); // Sicherstellen, dass der ungültige Token weg ist.
            navigate('/login', { replace: true });
        }
    }, [isLoading, isError, navigate]);

    const hasToken = !!localStorage.getItem('authToken');

    // Wenn kein Token da ist, wissen wir sofort, dass der User nicht eingeloggt ist.
    // Wir brauchen nicht auf das Ergebnis einer fehlgeschlagenen Query zu warten.
    if (!hasToken) {
        return <Navigate to="/login" replace />;
    }

    // Wenn ein Token da ist, aber die Query noch lädt, zeigen wir den Ladebildschirm.
    if (isLoading) {
        return <AppLoading />;
    }

    // Wenn die Query erfolgreich war, darf der User passieren.
    if (user) {
        return <Outlet />;
    }

    // Für den kurzen Moment, in dem `isError` true wird, bevor der useEffect umleitet,
    // rendern wir nichts oder den Loader, um ein Flackern zu vermeiden.
    return <AppLoading />;
}