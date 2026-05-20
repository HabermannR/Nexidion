// src/features/nodes/hooks/useSaveNodeContent.js

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import apiClient from '../../../api/apiClient.js';
import { useToast } from '../../../components/ToastProvider.jsx';

/**
 * Central hook for saving node content/title.
 * Shows a toast on error so save failures are never silent.
 */
export const useSaveNodeContent = (options = {}) => {
    const { vaultId: paramVaultId } = useParams();
    const queryClient = useQueryClient();
    const toast = useToast();

    const { onSuccess: callerOnSuccess, onError: callerOnError, ...restOptions } = options;

    return useMutation({
        mutationFn: ({ nodeId, title, content }) => {
            if (!nodeId || !paramVaultId) {
                return Promise.reject(new Error("Vault ID or Node ID is missing."));
            }

            const payload = { title, content };
            return apiClient.put(`/api/vaults/${paramVaultId}/nodes/${nodeId}`, payload);
        },
        onSuccess: (data, variables, context) => {
            const { nodeId } = variables;

            queryClient.invalidateQueries({ queryKey: ['versions', paramVaultId, nodeId] });
            queryClient.invalidateQueries({ queryKey: ['vaultTree', paramVaultId] });

            if (callerOnSuccess) {
                callerOnSuccess(data, variables, context);
            }
        },
        onError: (err, variables, context) => {
            const status = err.response?.status;
            let message = 'Failed to save changes.';

            if (status === 403) {
                message = 'You don\'t have permission to edit this node.';
            } else if (status === 429) {
                message = 'Node limit reached. Upgrade to save more nodes.';
            } else if (status === 404) {
                message = 'Node not found — it may have been deleted.';
            } else if (err.response?.data?.error) {
                message = err.response.data.error;
            }

            toast.error(message);

            if (callerOnError) {
                callerOnError(err, variables, context);
            }
        },
        ...restOptions,
    });
};
