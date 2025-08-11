// src/features/project-tree/useVaultTreeQuery.js
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient.js';

/**
 * Ein wiederverwendbarer Hook, um die Baumstruktur (die Node-Liste) für eine spezifische Vault abzurufen.
 * @param {string | number} vaultId - Die ID des Vaults, dessen Baum geladen werden soll.
 */
export const useVaultTreeQuery = (vaultId) => {
    return useQuery({
        // Der Query-Key enthält die vaultId, um sicherzustellen, dass die Bäume
        // verschiedener Vaults separat gecached werden.
        queryKey: ['vaultTree', vaultId],

        // Die queryFn wird nur ausgeführt, wenn eine vaultId vorhanden ist.
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/?format=list`).then(res => res.data),

        // WICHTIG: Die Abfrage wird erst dann aktiviert ('enabled'), wenn eine gültige vaultId
        // übergeben wird. Das verhindert unnötige API-Aufrufe mit 'undefined'.
        enabled: !!vaultId,
    });
};