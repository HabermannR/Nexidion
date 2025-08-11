// src/features/nodes/hooks/useVaultTreeQuery.js

import { useQuery } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient.js';

/**
 * Wandelt eine hierarchische Baumstruktur in eine flache Liste um.
 * @param {Array} tree - Die hierarchische Baumstruktur (Array von Wurzelknoten).
 * @returns {Array} Eine flache Liste aller Knoten im Baum.
 */
const flattenTree = (tree) => {
    const flatList = [];
    if (!Array.isArray(tree)) return flatList;

    const stack = [...tree]; // Starte mit den Wurzelknoten

    while (stack.length > 0) {
        const node = stack.pop(); // Nimm den nächsten Knoten vom Stapel
        if (!node) continue;

        // Füge den aktuellen Knoten zur flachen Liste hinzu
        // WICHTIG: Wir extrahieren den Knoten OHNE seine Kinder, um unendliche Rekursionen in der Darstellung zu vermeiden
        const { children, ...nodeWithoutChildren } = node;
        flatList.push(nodeWithoutChildren);

        // Wenn der Knoten Kinder hat, füge sie dem Stapel hinzu, um sie als Nächstes zu verarbeiten
        if (Array.isArray(children) && children.length > 0) {
            stack.push(...children);
        }
    }
    return flatList;
};

export const useVaultTreeQuery = (vaultId) => {
    return useQuery({
        // ACHTUNG: Der queryKey ist immer noch 'vaultTree', das ist ok.
        queryKey: ['vaultTree', vaultId],

        // Wir rufen jetzt den Endpunkt auf, der den Baum liefert.
        // Falls es einen expliziten Endpunkt für den Baum gibt, wäre `?format=tree` hier sinnvoll.
        // Wenn `?format=list` den Baum zurückgibt, ist das auch okay, aber verwirrend benannt.
        // Wir nehmen an, der gezeigte Endpunkt ist der richtige.
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/`).then(res => res.data),
        enabled: !!vaultId,

        // DER `select`-TEIL IST JETZT KORRIGIERT.
        select: (apiResponseTree) => {
            // Die API gibt uns direkt die Baumstruktur. Das ist super!
            const tree = apiResponseTree || [];

            // Wir berechnen jetzt die flache Liste aus dem Baum.
            const allNodesFlat = flattenTree(tree);


            // Wir geben die Struktur zurück, die alle Komponenten erwarten.
            return {
                tree: tree, // Die originale Baumstruktur
                allNodesFlat: allNodesFlat, // Die neu generierte flache Liste
            };
        },
    });
};