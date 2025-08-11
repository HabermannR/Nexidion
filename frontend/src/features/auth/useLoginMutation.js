// src/features/auth/useLoginMutation.js
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/apiClient';

export function useLoginMutation() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (credentials) => apiClient.post('/api/auth/login/', credentials),
        onSuccess: (data) => {
            const accessToken = data.data.access_token;
            localStorage.setItem('authToken', accessToken);

            // Signal an alle 'user' und 'vaults' Abfragen, sich neu zu laden.
            queryClient.invalidateQueries({ queryKey: ['user'] });
            queryClient.invalidateQueries({ queryKey: ['vaults'] });

            // Wir navigieren einfach zur Wurzel. Der "Lotse" (VaultIndexRedirector) übernimmt dort.
            navigate('/');
        },
        onError: (error) => {
            console.error('Login-Mutation fehlgeschlagen', error);
        }
    });
}