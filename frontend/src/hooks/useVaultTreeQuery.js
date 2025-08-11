import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/apiClient';

/**
 * Helper-Funktion, um den Baum zu einer flachen Liste von Nodes zu machen.
 * Diese Logik wird hier zentralisiert.
 */
const flattenTree = (nodes) => {
    if (!nodes || nodes.length === 0) return [];
    const flatList = [];
    const recurse = (nodesToFlatten) => {
        for (const node of nodesToFlatten) {
            const { children, ...rest } = node;
            flatList.push(rest);
            if (children && children.length > 0) {
                recurse(children);
            }
        }
    };
    recurse(nodes);
    return flatList;
};

/**
 * Dedizierter, wiederverwendbarer Hook, um die Baumdaten für einen Vault abzurufen.
 * Kapselt die Logik zum Fetchen und Transformieren der Daten.
 * @param {string} vaultId - Die ID des Vaults.
 * @param {object} [options] - Zusätzliche Optionen für useQuery (z.B. `enabled`).
 */
export const useVaultTreeQuery = (vaultId, options = {}) => {
    const queryResult = useQuery({
        // Der Query Key enthält die vaultId, um sicherzustellen, dass die Daten
        // pro Vault gecacht werden.
        queryKey: ['vaultTree', vaultId],

        // Die queryFn ruft die Daten von der API ab.
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes?format=tree`).then(res => res.data),

        // Der Query wird nur ausgeführt, wenn eine vaultId vorhanden ist.
        // Zusätzliche Bedingungen aus den Optionen können dies erweitern.
        enabled: !!vaultId && (options.enabled === undefined || options.enabled),

        // Standardmäßig werden leere Arrays zurückgegeben, um null/undefined-Prüfungen zu vermeiden.
        initialData: [],

        ...options,
    });

    // Abgeleitete Daten werden direkt im Hook mit useMemo berechnet.
    // Komponenten, die diesen Hook nutzen, erhalten die transformierten Daten direkt.
    const allNodesFlat = useMemo(() => flattenTree(queryResult.data), [queryResult.data]);

    return {
        ...queryResult,
        treeData: queryResult.data, // Umbenennung für Klarheit und Konsistenz
        allNodesFlat,
    };
};