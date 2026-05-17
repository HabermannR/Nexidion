import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/apiClient';

export function useGuestLoginMutation() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => apiClient.post('/api/auth/guest'),
        onSuccess: (response) => {
            const accessToken = response.data.access_token;
            localStorage.setItem('authToken', accessToken);
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
            queryClient.clear();
            navigate('/');
        },
        onError: (error) => {
            console.error('Guest login failed:', error);
        }
    });
}