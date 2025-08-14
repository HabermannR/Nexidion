// IN: src/services/queries/useResolveLinksQuery.js

import { useQuery } from '@tanstack/react-query';
// Importiere deinen zentralen API-Client. Ich nehme hier einen Platzhalter an.
import apiClient from '../../../api/apiClient';

/**
 * Ein dedizierter Query-Hook, um eine Liste von Link-Zielen aufzulösen.
 * @param {number} vaultId - Die ID des Vaults, in dem gesucht werden soll.
 * @param {string[]} targets - Ein Array von Link-Zielen (UUIDs oder Titel).
 */
export const useResolveLinksQuery = (vaultId, targets) => {
    return useQuery({
        // Der Query-Schlüssel ist entscheidend. Er enthält alle Abhängigkeiten.
        queryKey: ['links', 'resolve', vaultId, targets],

        // Die Query-Funktion, die die API aufruft.
        queryFn: async () => {
            // Wenn keine Ziele vorhanden sind, machen wir keine API-Anfrage.
            if (!targets || targets.length === 0) {
                return { results: {} }; // Gib eine leere, aber gültige Struktur zurück.
            }
            // Rufe den POST-Endpunkt über deinen zentralen API-Client auf.
            // Der Client sollte die Authentifizierung etc. handhaben.
            const response = await apiClient.post(
                `/vaults/${vaultId}/nodes/resolve-links`,
                { targets }
            );
            return response.data; // TanStack Query erwartet, dass ein Promise mit den Daten zurückgegeben wird.
        },

        // Wichtige Optionen für diesen spezifischen Anwendungsfall:
        // 'enabled' stellt sicher, dass die Abfrage nur ausgeführt wird, wenn vaultId und targets vorhanden sind.
        enabled: !!vaultId && Array.isArray(targets),

        // Diese Daten sind relativ statisch. Wir können sie für eine Weile cachen.
        // Ein Benutzer wird nicht ständig Links umbenennen.
        staleTime: 5 * 60 * 1000, // 5 Minuten
        // Behalte die Daten im Cache, auch wenn keine Komponente sie mehr verwendet.
        gcTime: 10 * 60 * 1000, // 10 Minuten
    });
};