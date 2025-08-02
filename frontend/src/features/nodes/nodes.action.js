// src/features/nodes/nodes.action.js (ANGEPASST AN API v3)

import {redirect} from "react-router-dom";
import apiClient from "../../api/apiClient";
import {useContextStore} from "../context/contextStore";

export async function nodeAction({request, params}) {
    const {vaultId, nodeId} = params;
    const formData = await request.formData();
    const intent = formData.get("intent");

    // --- INTENT: INHALT AKTUALISIEREN ---
    if (intent === "updateContent") {
        let content = formData.get("content");
        const title = formData.get("title"); // Wichtig: Titel mitlesen für PUT

        // Deine "Daten-Hygiene"-Logik bleibt hier super.
        if (typeof content === "string") {
            const trimmedContent = content.trim();
            if (trimmedContent.startsWith("# ")) {
                const firstNewlineIndex = trimmedContent.indexOf("\n");
                content =
                    firstNewlineIndex !== -1
                        ? trimmedContent.substring(firstNewlineIndex + 1).trim()
                        : "";
            }
        }

        try {
            // API v3: Versionierte Updates laufen über PUT
            await apiClient.put(`/api/vaults/${vaultId}/nodes/${nodeId}`, {
                title: title, // Der Titel wird mitgesendet, um ihn nicht versehentlich zu löschen
                content: content,
            });
            return {ok: true};
        } catch (error) {
            const errorMessage = error.response?.data?.error || "Fehler beim Speichern.";
            return {ok: false, error: errorMessage};
        }
    }

    // --- INTENT: NODE UMBENENNEN ---
    if (intent === "renameNode") {
        const newTitle = formData.get("title");
        if (!newTitle) return {ok: false, error: "Kein Titel angegeben."};

        try {
            // API v3: Versionierte Updates laufen über PUT
            await apiClient.put(`/api/vaults/${vaultId}/nodes/${nodeId}`, {
                title: newTitle,
            });
            return {ok: true, message: "Node umbenannt."};
        } catch (error) {
            const errorMessage = error.response?.data?.error || "Fehler beim Umbenennen.";
            return {ok: false, error: errorMessage};
        }
    }

    // --- NEU - INTENT: ICON ÄNDERN ---
    if (intent === "changeIcon") {
        const icon = formData.get("icon");
        try {
            // API v3: Icon-Änderung über den neuen PATCH-Endpunkt
            await apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeId}/icon`, {
                icon: icon,
            });
            return {ok: true, message: "Icon geändert."};
        } catch (error) {
            const errorMessage = error.response?.data?.error || "Fehler beim Ändern des Icons.";
            return {ok: false, error: errorMessage};
        }
    }

    // ==========================================================
    // NEU - INTENT 3: NODE LÖSCHEN
    // ==========================================================
    if (intent === "deleteNode") {
        try {
            // Ruft den DELETE-Endpunkt der API auf.
            await apiClient.delete(`/api/vaults/${vaultId}/nodes/${nodeId}`);

            // 2. NEU: Node aus dem globalen Zustand entfernen.
            // Wir greifen via getState() auf die Aktionen zu, da dies keine React-Komponente ist.
            const {removeNodeFromContext} = useContextStore.getState();
            removeNodeFromContext(nodeId);

            // 3. Nach dem Löschen leiten wir den Benutzer um.
            return redirect(`/vaults/${vaultId}`);
        } catch (error) {
            const errorMessage =
                error.response?.data?.error || "Fehler beim Löschen.";
            console.error("Fehler beim Löschen des Nodes:", errorMessage);
            return {ok: false, error: errorMessage};
        }
    }

    // Fallback, falls ein unbekannter Intent gesendet wird.
    throw new Response(`Unbekannter Intent: ${intent}`, {status: 400});
}
