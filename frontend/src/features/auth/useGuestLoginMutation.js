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
        // No onError override — letting the error propagate to the mutation's `error`
        // state so LoginPage can render the guestError alert block. Previously this
        // was swallowing all errors with only a console.error, leaving the user with
        // a de-spun button and no feedback (soft-lock).
    });
}
