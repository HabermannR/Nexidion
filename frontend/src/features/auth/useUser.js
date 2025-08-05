// IN: src/features/auth/useUser.js

import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';

export function useUser() {
    return useQuery({
        // Dieser Key ist global und eindeutig für den eingeloggten Benutzer.
        queryKey: ['currentUser'],

        // Die Funktion ruft den /api/auth/me Endpunkt auf.
        queryFn: async () => {
            try {
                const response = await apiClient.get('/api/auth/me');
                return response.data.user; // Gibt nur das User-Objekt zurück
            } catch (error) {
                // Wenn der /me Endpunkt fehlschlägt (z.B. 401), bedeutet das,
                // dass der Benutzer nicht eingeloggt ist. Wir werfen den Fehler,
                // damit React Query ihn als `isError` behandeln kann.
                console.error("Failed to fetch user:", error);
                throw error;
            }
        },

        // Wichtige Optionen für Authentifizierungsdaten:
        staleTime: 1000 * 60 * 5, // User-Daten ändern sich selten, 5 Minuten stale time sind ok.
        retry: 1, // Bei einem 401-Fehler nicht unendlich oft neu versuchen.
        refetchOnWindowFocus: false, // Es ist unnötig, bei jedem Fokus-Wechsel den User neu zu laden.
    });
}