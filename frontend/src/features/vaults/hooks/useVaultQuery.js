// src/features/vaults/hooks/useVaultQuery.js

import { useQuery } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient.js';

/**
 * Ein wiederverwendbarer Hook, um die Metadaten für eine einzelne Vault abzurufen.
 * @param {string} vaultId - Die ID des Vaults.
 */
export const useVaultQuery = (vaultId) => {
    return useQuery({
        // Query-Key ist spezifisch für eine einzelne Vault.
        queryKey: ['vault', vaultId],

        // Holt die Daten für genau diese eine Vault.
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}`).then(res => res.data),

        // Die Abfrage ist nur aktiv, wenn eine vaultId vorhanden ist.
        enabled: !!vaultId,
    });
};