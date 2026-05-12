// src/features/auth/useUserQuery.js
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';

export const useUserQuery = () => {
    const token = localStorage.getItem('authToken');

    return useQuery({
        queryKey: ['user'],
        queryFn: () => apiClient.get('/api/auth/me').then(res => res.data),

        // Führe die Query nur aus, wenn ein Token existiert.
        enabled: !!token,

        // Das hier repariert den doppelten Request!
        staleTime: Infinity,
        gcTime: Infinity,

        retry: (failureCount, error) => {
            if (error.response?.status === 401 || error.response?.status === 404) {
                return false; // Bei Auth-Fehlern nicht wiederholen.
            }
            return failureCount < 1;
        },
    });
};