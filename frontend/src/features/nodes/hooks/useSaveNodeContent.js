// src/features/nodes/hooks/useSaveNodeContent.js

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import apiClient from '../../../api/apiClient.js';

/**
 * Ein zentraler, wiederverwendbarer Hook zum Speichern/Aktualisieren
 * des Inhalts und Titels eines Nodes.
 *
 * Er übernimmt die PUT-Anfrage und kümmert sich um die automatische
 * Invalidierung der relevanten Caches (Versionen und Baumstruktur).
 *
 * @param {object} options - Zusätzliche Optionen für useMutation (z.B. onSuccess, onError).
 * @returns {object} Die Mutation-Instanz von TanStack Query.
 */
export const useSaveNodeContent = (options = {}) => {
    const { vaultId: paramVaultId } = useParams();
    const queryClient = useQueryClient();

    // Destructure callbacks from options to prevent them from being overwritten by the spread.
    const { onSuccess: callerOnSuccess, onError: callerOnError, ...restOptions } = options;

    return useMutation({
        mutationFn: ({ nodeId, title, content }) => {
            // Use the vaultId from params as the source of truth.
            if (!nodeId || !paramVaultId) {
                return Promise.reject(new Error("Vault ID or Node ID is missing."));
            }

            const payload = { title, content };
            return apiClient.put(`/api/vaults/${paramVaultId}/nodes/${nodeId}`, payload);
        },
        onSuccess: (data, variables, context) => {
            const { nodeId } = variables;

            // --- THE FIX: This logic now runs reliably before the caller's onSuccess ---

            // 1. Invalidate the specific content/versions of the updated node.
            //    This will cause NodeContent.jsx or similar components to refetch.
            queryClient.invalidateQueries({ queryKey: ['versions', paramVaultId, nodeId] });

            // 2. Invalidate the entire tree.
            //    This is crucial if the node's title changed, so the tree view updates.
            queryClient.invalidateQueries({ queryKey: ['vaultTree', paramVaultId] });

            // Now, execute any additional onSuccess logic from the calling component.
            if (callerOnSuccess) {
                callerOnSuccess(data, variables, context);
            }
        },
        onError: (err, variables, context) => {
            // Execute additional onError logic from the calling component, if provided.
            if (callerOnError) {
                callerOnError(err, variables, context);
            }
        },
        // Spread the remaining options, which no longer include onSuccess or onError.
        ...restOptions,
    });
};