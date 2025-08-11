// src/features/auth/useUserQuery.js
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient'; // Pfad anpassen

export const useUserQuery = () => {
    return useQuery({
        queryKey: ['user'],
        queryFn: () => apiClient.get('/api/auth/me').then(res => res.data),
        // Wichtige Optionen für eine User-Query:
        staleTime: Infinity, // User-Daten ändern sich selten, also nicht ständig neu laden.
        gcTime: Infinity, // Garbage-Collection-Zeit
        retry: 1, // Bei Fehler (z.B. ungültiger Token) nicht endlos versuchen.
    });
};