// src/features/nodes/nodes.loader.js

import apiClient from '../../api/apiClient';

const loadTree = async (vaultId) => {
    // 1. Logge den Start
    console.log(`[Loader] Starte Ladevorgang für Vault-ID: ${vaultId}. Warte 2 Sekunden...`);

    const response = await apiClient.get(`/api/vaults/${vaultId}/nodes?format=tree`);

    // 2. Logge das Ende
    console.log("[Loader] Ladevorgang abgeschlossen. Gebe Daten zurück.");
    return response.data;
};

export function vaultTreeLoader({ params }) {
    return loadTree(params.vaultId);
}