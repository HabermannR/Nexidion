// src/features/workspace/nodes.action.js

import { redirect } from "react-router-dom";
import apiClient from "../../api/apiClient.js";
import { useWorkspaceStore } from "./workspaceStore.js";

/**
 * RADIKALE VEREINFACHUNG: Alle erfolgreichen Mutationen redirecten zur sauberen URL.
 * Dadurch zeigen sie automatisch die neueste Version, ohne komplexe useEffect-Logik.
 */
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
                title: formData.get("title"), // Titel mitsenden damit er nicht überschrieben wird
            };

            await apiClient.put(`/api/vaults/${vaultId}/nodes/${nodeId}`, payload);
            console.log('[ACTION] updateContent erfolgreich - redirect zur sauberen URL');

            // REDIRECT statt return {ok: true} - das ist der Schlüssel!
            return redirect(`/vaults/${vaultId}/nodes/${nodeId}`);
        }

        // --- INTENT: TITEL ÄNDERN ---
        if (intent === "renameNode") {
            const payload = {
                title: formData.get("title"),
                content: formData.get("content"), // Inhalt mitsenden damit er nicht verloren geht
            };

            await apiClient.put(`/api/vaults/${vaultId}/nodes/${nodeId}`, payload);
            console.log('[ACTION] renameNode erfolgreich - redirect zur sauberen URL');

            return redirect(`/vaults/${vaultId}/nodes/${nodeId}`);
        }

        // --- INTENT: ICON ÄNDERN ---
        if (intent === "changeIcon") {
            console.log(`[ACTION] Intent 'changeIcon' erkannt. Icon-Payload:`, formData.get("icon"));

            await apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeId}/icon`, {
                icon: formData.get("icon"),
            });

            console.log('[ACTION] changeIcon erfolgreich - redirect zur sauberen URL');

            // AUCH HIER: Redirect statt return {ok: true}
            return redirect(`/vaults/${vaultId}/nodes/${nodeId}`);
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
            return redirect(`/vaults/${vaultId}/nodes/${newNode.id}`);
        }

        // --- INTENT: NODE LÖSCHEN ---
        if (intent === "deleteNode") {
            // Holen die parentId aus den Formulardaten
            const parentId = formData.get("parentId");

            await apiClient.delete(`/api/vaults/${vaultId}/nodes/${nodeId}`);

            // Lokalen Zustand aufräumen
            //useWorkspaceStore.getState().removeNodeFromContext(nodeId);

            // Entscheiden, wohin umgeleitet wird
            if (parentId) {
                console.log(`[ACTION] deleteNode erfolgreich - redirect zum Parent-Node ${parentId}`);
                return redirect(`/vaults/${vaultId}/nodes/${parentId}`);
            } else {
                console.log('[ACTION] deleteNode erfolgreich - redirect zur Vault-Wurzel (kein Parent)');
                return redirect(`/vaults/${vaultId}`);
            }
        }

        // Fallback für unbekannte Intents
        throw new Response(`Unbekannter Intent: ${intent}`, { status: 400 });

    } catch (error) {
        const errorMessage = error.response?.data?.error || "Ein unbekannter Fehler ist aufgetreten.";
        console.error(`[NODE ACTION] Fehler bei Intent '${intent}':`, errorMessage);

        // Bei Fehlern geben wir KEIN redirect zurück, sondern ein Fehlerobjekt
        // Das erlaubt der UI, den Fehler anzuzeigen
        return { ok: false, error: errorMessage };
    }
}