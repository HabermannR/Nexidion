import { useQuery, keepPreviousData } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient';

/**
 * Ruft die API auf, um nach Nodes für die Autocomplete-Funktion zu suchen.
 * Diese Funktion ist privat für diesen Hook und wird nicht exportiert.
 * @param {string} vaultId - Die ID des Vaults, in dem gesucht wird.
 * @param {string} query - Der vom Benutzer eingegebene Suchbegriff.
 * @returns {Promise<Array<{id: string, title: string}>>} - Eine Liste von passenden Nodes.
 */
const searchNodes = async (vaultId, query) => {
    try {
        const response = await apiClient.get(`/api/vaults/${vaultId}/nodes/search`, {
            params: { q: query } // axios kümmert sich um das URL-Encoding
        });
        return response.data || []; // Stelle sicher, dass immer ein Array zurückgegeben wird
    } catch (error) {
        console.error("Fehler bei der Node-Suche für Autocomplete:", error);
        // Wirf den Fehler weiter, damit TanStack Query ihn als 'isError' markieren kann.
        throw error;
    }
};

/**
 * Ein Custom Hook, der die Logik für die Node-Suche im Editor kapselt.
 * Er liefert eine Liste von Node-Vorschlägen basierend auf einem Suchbegriff.
 *
 * @param {string} vaultId - Die ID des Vaults.
 * @param {string} searchTerm - Der aktuelle Suchbegriff aus dem Editor.
 */
export const useNodeSearchQuery = (vaultId, searchTerm) => {
    return useQuery({
        // Der queryKey enthält den vaultId und den searchTerm, damit die Anfrage
        // bei Änderungen automatisch neu ausgeführt und gecacht wird.
        queryKey: ['nodeSearch', vaultId, searchTerm],

        // Die Funktion, die die Daten abruft.
        queryFn: () => searchNodes(vaultId, searchTerm),

        // WICHTIGE OPTIMIERUNG:
        // Die Abfrage wird nur ausgeführt, wenn alle Bedingungen erfüllt sind.
        // Das verhindert unnötige API-Anfragen bei jedem Tastendruck.
        enabled:
            !!vaultId &&              // Es muss eine vaultId vorhanden sein.
            !!searchTerm &&           // Der Suchbegriff darf nicht leer sein.
            searchTerm.length >= 2,   // Der Nutzer muss mindestens 2 Zeichen getippt haben.

        // UX-Verbesserung: Zeigt die alten Ergebnisse an, während neue geladen werden.
        // Verhindert ein "Flackern" der Ergebnisliste.
        placeholderData: keepPreviousData,

        // Die Ergebnisse der Autocomplete-Suche sind oft nur kurz relevant.
        // Wir können sie schneller als "stale" markieren, damit sie bei Bedarf
        // schneller neu geladen werden.
        staleTime: 60 * 1000, // 1 Minute
    });
};