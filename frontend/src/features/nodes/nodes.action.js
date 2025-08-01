// src/features/nodes/nodes.action.js (KORRIGIERTE VERSION)

import { redirect } from "react-router-dom"; // Wichtig für die Umleitung nach dem Löschen
import apiClient from "../../api/apiClient";

/**
 * Verarbeitet schreibende Aktionen für Nodes, die über Form-Submits ausgelöst werden.
 */
export async function nodeAction({ request, params }) {
  const { vaultId, nodeId } = params;
  const formData = await request.formData();
  const intent = formData.get("intent");

  // ==========================================================
  // INTENT 1: INHALT AKTUALISIEREN
  // ==========================================================
  if (intent === "updateContent") {
    // HINWEIS: Du hast hier fälschlicherweise 'title' mitgesendet,
    // obwohl das Formular nur 'content' hat. Ich habe das korrigiert.
    // Außerdem hast du apiClient.put verwendet, aber die Form und API erwarten PATCH.
    let content = formData.get("content");

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
      // Die Form sendet `method="patch"`, also sollte hier auch `patch` verwendet werden.
      // Die API für Titel- UND Inhaltsänderung sollte über PUT oder PATCH laufen.
      // Ich nehme an, deine API kann mit PATCH auch den Inhalt aktualisieren.
      await apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeId}`, {
        content: content, // Nur den Inhalt senden
      });
      return { ok: true };
    } catch (error) {
      const errorMessage =
        error.response?.data?.error || "Fehler beim Speichern des Inhalts.";
      console.error("Fehler beim Speichern des Node-Inhalts:", errorMessage);
      return { ok: false, error: errorMessage };
    }
  }

  // ==========================================================
  // NEU - INTENT 2: NODE UMBENENNEN
  // ==========================================================
  if (intent === "renameNode") {
    const newTitle = formData.get("title");
    if (!newTitle) {
      return { ok: false, error: "Kein Titel angegeben." };
    }

    try {
      // Ruft den PATCH-Endpunkt der API auf, genau wie in Flask definiert.
      await apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeId}`, {
        title: newTitle,
      });
      // Es ist wichtig, etwas zurückzugeben, damit React Router weiß, dass es erfolgreich war.
      return { ok: true, message: "Node umbenannt." };
    } catch (error) {
      const errorMessage =
        error.response?.data?.error || "Fehler beim Umbenennen.";
      console.error("Fehler beim Umbenennen des Nodes:", errorMessage);
      return { ok: false, error: errorMessage };
    }
  }

  // ==========================================================
  // NEU - INTENT 3: NODE LÖSCHEN
  // ==========================================================
  if (intent === "deleteNode") {
    try {
      // Ruft den DELETE-Endpunkt der API auf.
      await apiClient.delete(`/api/vaults/${vaultId}/nodes/${nodeId}`);
      // Nach dem Löschen leiten wir den Benutzer um, z.B. zur Vault-Übersicht.
      return redirect(`/vaults/${vaultId}`);
    } catch (error) {
      const errorMessage =
        error.response?.data?.error || "Fehler beim Löschen.";
      console.error("Fehler beim Löschen des Nodes:", errorMessage);
      return { ok: false, error: errorMessage };
    }
  }

  // Fallback, falls ein unbekannter Intent gesendet wird.
  throw new Response(`Unbekannter Intent: ${intent}`, { status: 400 });
}
