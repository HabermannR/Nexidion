// src/features/workspace/nodes.action.js

import { redirect } from "react-router-dom";
import apiClient from "../../api/apiClient.js";


// WICHTIG: Füge einen Timestamp als Query-Parameter hinzu, um Cache zu umgehen
const createFreshRedirect = (path) => {
    const url = new URL(path, 'http://localhost'); // Base URL nur für URL-Konstruktion
    url.searchParams.set('_t', Date.now().toString());
    return redirect(url.pathname + url.search);
};

export async function nodeAction({ request, params }) {
    const { vaultId, nodeId } = params;
    const formData = await request.formData();
    const intent = formData.get("intent");

    console.log(`[NODE ACTION] Empfangener Intent: '${intent}' für Node ${nodeId}`);

    try {
        // --- INTENT: INHALT ÄNDERN ---
        if (intent === "updateContent") {
            const payload = {
                content: formData.get("content"),
                title: formData.get("title"),
            };

            await apiClient.put(`/api/vaults/${vaultId}/nodes/${nodeId}`, payload);
            console.log('[ACTION] updateContent erfolgreich - redirect zur sauberen URL');

            return createFreshRedirect(`/vaults/${vaultId}/nodes/${nodeId}`);
        }

        // --- INTENT: TITEL ÄNDERN ---
        if (intent === "renameNode") {
            const payload = {
                title: formData.get("title"),
                content: formData.get("content"),
            };

            await apiClient.put(`/api/vaults/${vaultId}/nodes/${nodeId}`, payload);
            console.log('[ACTION] renameNode erfolgreich - redirect zur sauberen URL');

            return createFreshRedirect(`/vaults/${vaultId}/nodes/${nodeId}`);
        }

        // --- INTENT: ICON ÄNDERN ---
        if (intent === "changeIcon") {
            console.log(`[ACTION] Intent 'changeIcon' erkannt. Icon-Payload:`, formData.get("icon"));

            await apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeId}/icon`, {
                icon: formData.get("icon"),
            });

            console.log('[ACTION] changeIcon erfolgreich - redirect zur sauberen URL');

            return createFreshRedirect(`/vaults/${vaultId}/nodes/${nodeId}`);
        }

        // --- INTENT: NEUEN NODE ERSTELLEN ---
        if (intent === "createNode") {
            const parentId = formData.get("parentId");
            const title = formData.get("title") || "Neues Dokument";

            const response = await apiClient.post(`/api/vaults/${vaultId}/nodes`, {
                title: title,
                parent_id: parentId,
            });
            const newNode = response.data;

            console.log('[ACTION] createNode erfolgreich - redirect zum neuen Node');
            return createFreshRedirect(`/vaults/${vaultId}/nodes/${newNode.id}`);
        }

        // --- INTENT: NODE LÖSCHEN ---
        if (intent === "deleteNode") {
            const parentId = formData.get("parentId");

            await apiClient.delete(`/api/vaults/${vaultId}/nodes/${nodeId}`);

            // Entscheiden, wohin umgeleitet wird
            if (parentId) {
                console.log(`[ACTION] deleteNode erfolgreich - redirect zum Parent-Node ${parentId}`);
                return createFreshRedirect(`/vaults/${vaultId}/nodes/${parentId}`);
            } else {
                console.log('[ACTION] deleteNode erfolgreich - redirect zur Vault-Wurzel (kein Parent)');
                return createFreshRedirect(`/vaults/${vaultId}`);
            }
        }

        // Fallback für unbekannte Intents
        throw new Response(`Unbekannter Intent: ${intent}`, { status: 400 });

    } catch (error) {
        const errorMessage = error.response?.data?.error || "Ein unbekannter Fehler ist aufgetreten.";
        console.error(`[NODE ACTION] Fehler bei Intent '${intent}':`, errorMessage);

        return { ok: false, error: errorMessage };
    }
}