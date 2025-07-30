import apiClient from '../../api/apiClient';
import { redirect } from 'react-router-dom';
import { checkAuth } from '../auth/auth.helpers';

// ===================================================================
// --- LOADER 1: FÜR DEN BAUM & DIE START-UMLEITUNG ---
// ===================================================================

/**
 * Lädt die gesamte Baumstruktur für einen Vault.
 * Hat eine zusätzliche "Lotsen"-Funktion: Wenn keine spezifische Node-URL aufgerufen wird,
 * leitet er automatisch zum ersten Knoten im Baum weiter.
 * @param {object} { params } - Von React Router bereitgestellte Objekte.
 */
export async function vaultTreeLoader({ params }) {
    if (!checkAuth()) {
        return null;
    }
    console.log(`[VAULT TREE LOADER] Lade Baum für Vault ${params.vaultId}`);
    const response = await apiClient.get(`/api/vaults/${params.vaultId}/nodes?format=tree&v3=true`);
    return response.data;
}


// ===================================================================
// --- LOADER 2: FÜR DEN INHALT EINES EINZELNEN NODES ---
// ===================================================================

/**
 * Lädt die detaillierten Daten (inkl. Inhalt) für einen einzelnen, spezifischen Node.
 * @param {object} { params } - Von React Router bereitgestellte Objekte.
 */
export async function nodeContentLoader({ params }) {
    console.log(`[Node Content Loader] Lade Inhalt für Node: ${params.nodeId}`);

    try {
        const response = await apiClient.get(
            `/api/vaults/${params.vaultId}/nodes/${params.nodeId}`
        );
        return response.data;
    } catch (error) {
        console.error(`[Node Content Loader] Fehler beim Laden des Inhalts für Node ${params.nodeId}:`, error);
        throw error;
    }
}


// ===================================================================
// --- LOADER 3: NUR FÜR DIE VERSIONSHISTORIE (ON-DEMAND) ---
// ===================================================================

/**
 * Lädt den kompletten Versionsverlauf für einen einzelnen Node.
 * Wird über einen `fetcher` bei Bedarf aufgerufen, um die initiale Ladezeit zu optimieren.
 * @param {object} { params } - Von React Router bereitgestellte Objekte.
 */
export async function nodeVersionsLoader({ params }) {
    console.log(`[Versions Loader] Lade Verlauf für Node: ${params.nodeId}`);
    try {
        const response = await apiClient.get(
            `/api/vaults/${params.vaultId}/nodes/${params.nodeId}/versions`
        );
        return response.data;
    } catch (error) {
        console.error(`[Versions Loader] Fehler beim Laden des Verlaufs für Node ${params.nodeId}:`, error);
        throw error;
    }
}