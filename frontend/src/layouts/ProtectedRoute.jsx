// src/layouts/ProtectedRoute.jsx
import { Navigate, Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query'; // Verwenden wir direkt für Klarheit
import apiClient from '../api/apiClient';
import AppLoading from '../components/AppLoading';

// Dies ist unser dedizierter Hook, um den User zu holen.
// Er ersetzt den Datenteil des alten `protectedLoader`.
const useUserQuery = () => {
    return useQuery({
        queryKey: ['user'],
        queryFn: () => apiClient.get('/api/auth/me').then(res => res.data),
        retry: 1, // Bei Fehler nicht endlos versuchen
    });
}

export function ProtectedRoute() {
    // Wir prüfen den User-Status über einen Query.
    const { data: user, isLoading, isError } = useUserQuery();

    if (isLoading) {
        return <AppLoading />;
    }

    if (isError || !user) {
        // Token ungültig oder nicht vorhanden -> zurück zum Login.
        return <Navigate to="/login" replace />;
    }

    // Alles ok, der Gast darf eintreten und die geschützten Seiten sehen.
    return <Outlet />;
}