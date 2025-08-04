// src/features/workspace/nodes.loader.js

import apiClient from '../../api/apiClient.js';
import { checkAuth } from '../auth/auth.helpers.js';

/**
 * LOADER 1: Der Baum-Loader (für die WorkspaceLayout-Route)
 *
 * Verantwortlichkeit: Lädt NUR den kompletten Navigationsbaum für einen Vault.
 * Wird dank `shouldRevalidate` im Router nur bei einem Vault-Wechsel ausgeführt.
 */
export async function vaultTreeLoader({ params }) {
    // +++ DEBUG PRINT D2 (Baum) +++
    console.log(`[VAULT TREE LOADER] Ausgeführt für Vault ${params.vaultId} um ${new Date().toLocaleTimeString()}`);
    // Sicherheitscheck
    if (!checkAuth()) {
        return null;
    }
    console.log(`[VAULT TREE LOADER] Lade Baum für Vault ${params.vaultId}`);
    try {
        const response = await apiClient.get(`/api/vaults/${params.vaultId}/nodes?format=tree&v3=true`);
        // Gibt die reinen Baum-Daten zurück.
        return response.data;
    } catch (error) {
        console.error(`[VAULT TREE LOADER] FEHLER:`, error);
        // Wirft den Fehler, damit das `errorElement` im Router ihn fangen kann.
        throw error;
    }
}

/**
 * LOADER 2: Der Node-Detail-Loader (für die NodeContent-Route)
 *
 * Verantwortlichkeit: Lädt ALLE Versionen für einen EINZELNEN Node.
 * Wird bei jedem Klick auf einen neuen Node im Baum ausgeführt.
 */
export async function nodeDetailLoader({ params }) {
    // +++ DEBUG PRINT D2 (Details) +++
    console.log(`[NODE DETAIL LOADER] Ausgeführt für Node ${params.nodeId} um ${new Date().toLocaleTimeString()}`);
    // Sicherheitscheck
    if (!checkAuth()) {
        // Gibt ein leeres, aber gültiges Objekt zurück, um Fehler in der Komponente zu vermeiden.
        return { versions: [] };
    }
    const { vaultId, nodeId } = params;
    console.log(`[NODE DETAIL LOADER] Lade Versionen für Node ${nodeId}`);
    try {
        const response = await apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`);
        const versions = response.data || [];

        // +++ ENTSCHEIDENDER DEBUG PRINT +++
        console.log(`[NODE DETAIL LOADER] API-Antwort erhalten. Anzahl Versionen: ${versions.length}`);
        if (versions.length > 0) {
            // Finde die neueste Version (typischerweise die erste in der Liste)
            const latestVersion = versions[0];
            console.log(`[NODE DETAIL LOADER] Icon der NEUESTEN Version (v${latestVersion.version}) ist: '${latestVersion.icon}'`);

            // Optional, um das ganze Objekt zu sehen:
            // console.log('[NODE DETAIL LOADER] Neueste Version Objekt:', JSON.stringify(latestVersion));
        }

        return { versions };


    } catch (error) {
        console.error(`[NODE DETAIL LOADER] FEHLER:`, error);
        throw error;
    }
}