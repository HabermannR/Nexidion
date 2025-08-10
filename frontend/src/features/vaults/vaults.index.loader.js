// src/features/vaults/vaults.index.loader.js

import apiClient from '../../api/apiClient';
// WICHTIG: Importiere die `redirect`-Funktion von React Router.
import { redirect } from 'react-router-dom';

/**
 * Dieser Loader prüft, ob es einen Knoten gibt, zu dem umgeleitet werden kann.
 * Er löst bei Erfolg SOFORT einen redirect aus. Das ist effizient und verhindert Lade-Kaskaden.
 */
export async function vaultIndexLoader({ params }) {
    try {
        // Effizienter API-Aufruf: Wir brauchen nur den ersten Knoten, um zu wissen, ob der Vault leer ist.
        const response = await apiClient.get(`/api/vaults/${params.vaultId}/nodes?format=tree&limit=1`);
        const tree = response.data;

        // Fall 1: Der Vault hat mindestens einen Knoten.
        if (tree && tree.length > 0) {
            const firstNodeId = tree[0].id;
            // Gib eine Redirect-Response zurück. React Router stoppt den aktuellen
            // Ladevorgang und startet sofort einen neuen zur Ziel-URL.
            return redirect(`nodes/${firstNodeId}`);
        }

        // Fall 2: Der Vault ist leer.
        // Wir geben `null` zurück. Dadurch wird die an die Route gebundene Komponente
        // (`<VaultIndexRedirector>`) gerendert, die eine "Bitte wähle"-Nachricht anzeigt.
        return null;

    } catch (error) {
        console.error("Fehler im vaultIndexLoader:", error);
        // Im Fehlerfall auch einfach `null` zurückgeben. Die UI zeigt dann die
        // "Bitte wähle"-Nachricht an, was ein sicherer Fallback ist.
        return null;
    }
}