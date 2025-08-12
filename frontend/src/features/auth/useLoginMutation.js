// src/features/auth/useLoginMutation.js (NEUE, KORRIGIERTE VERSION)

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/apiClient';

export function useLoginMutation() {
    const navigate = useNavigate();
    const queryClient = useQueryClient(); // Wir brauchen ihn noch für den Reset

    return useMutation({
        mutationFn: (credentials) => apiClient.post('/api/auth/login', credentials),
        onSuccess: (response) => {
            // Schritt 1: Token aus der Antwort extrahieren und speichern.
            const accessToken = response.data.access_token;
            localStorage.setItem('authToken', accessToken);

            // Schritt 2: Den Token für zukünftige Anfragen im apiClient setzen.
            // Dies ist wichtig, damit der erste Aufruf von ProtectedRoute den Header hat.
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

            // Schritt 3: Den Query-Cache für einen sauberen Start zurücksetzen.
            // Dies entfernt alte Daten (z.B. von einem vorherigen, fehlgeschlagenen Login-Versuch).
            queryClient.clear();

            // Schritt 4: Zur Wurzel navigieren. Der Rest wird von ProtectedRoute gehandhabt.
            navigate('/');
        },
        onError: (error) => {
            // Optional: Alte 'user'-Query-Daten bei einem fehlgeschlagenen Login entfernen.
            queryClient.removeQueries({ queryKey: ['user'] });
            console.error('Login-Mutation fehlgeschlagen:', error);
        }
    });
}