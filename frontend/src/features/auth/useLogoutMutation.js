// src/features/auth/useLogoutMutation.js
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '../workspace/workspaceStore';

export function useLogoutMutation() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async () => {
            localStorage.removeItem('authToken');
        },
        onSuccess: () => {
            // Clear all cached query data for a clean slate.
            queryClient.clear();
            // Clear persisted workspace state (selection, collapsed nodes, saved sets)
            // so the next user doesn't inherit the previous session's UI state.
            useWorkspaceStore.getState().resetWorkspaceContext();
            navigate('/login');
        }
    });
}
