import apiClient from '../../api/apiClient';

/**
 * Verarbeitet schreibende Aktionen für Nodes, die über Form-Submits ausgelöst werden.
 */
export async function nodeAction({ request, params }) {
    const { vaultId, nodeId } = params;
    const formData = await request.formData();
    const intent = formData.get('intent');

    if (intent === 'updateContent') {
        const title = formData.get('title');
        let content = formData.get('content'); // `let`, da wir den Inhalt ändern

        console.log(`[Node Action] Intent: 'updateContent' für Node ${nodeId}`);

        // ==========================================================
        // NEUE, ROBUSTERE DATEN-HYGIENE LOGIK
        // ==========================================================
        if (typeof content === 'string') {
            const trimmedContent = content.trim();

            // Regel: Wenn der Text mit einer H1-Überschrift beginnt...
            if (trimmedContent.startsWith('# ')) {
                console.log("[Node Action] Inhalt beginnt mit H1. Prüfe auf Entfernung...");

                // Finde den ersten Zeilenumbruch. Das markiert das Ende der Titelzeile.
                const firstNewlineIndex = trimmedContent.indexOf('\n');

                if (firstNewlineIndex !== -1) {
                    // Wenn es weitere Zeilen gibt, nimm alles NACH der ersten Zeile.
                    content = trimmedContent.substring(firstNewlineIndex + 1).trim();
                } else {
                    // Wenn der Inhalt NUR aus der Titelzeile bestand, ist er jetzt leer.
                    content = '';
                }
            }
        }
        // ==========================================================

        try {
            await apiClient.put(
                `/api/vaults/${vaultId}/nodes/${nodeId}`,
                {
                    title: title,
                    content: content, // Sende den bereinigten Inhalt
                }
            );
            return { ok: true };
        } catch (error) {
            const errorMessage = error.response?.data?.error || "Ein unbekannter Fehler ist aufgetreten.";
            console.error("Fehler beim Speichern des Node-Inhalts:", errorMessage);
            return { ok: false, error: errorMessage };
        }
    }

    throw new Response(`Unbekannter Intent: ${intent}`, { status: 400 });
}