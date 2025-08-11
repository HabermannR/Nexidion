// src/features/auth/useLogoutMutation.js
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

export function useLogoutMutation() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async () => {
            localStorage.removeItem('authToken');
        },
        onSuccess: () => {
            // Alle Daten im Cache löschen für einen sauberen Zustand.
            queryClient.clear();
            navigate('/login');
        }
    });
}