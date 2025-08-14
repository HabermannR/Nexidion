import { useNavigate, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient'; // Dein zentraler API-Client

// Ein Query, um einen einzelnen Node anhand seines Titels zu finden.
const fetchNodeByTitle = async (vaultId, title) => {
    // Wir rufen den Endpunkt auf, den du bereitgestellt hast.
    const response = await apiClient.get(`/api/vaults/${vaultId}/nodes`, {
        params: {
            title: title // Der Query-Parameter ist `title`
        }
    });

    const data = response.data;
    // Das Backend gibt ein Array zurück. Wir wollen den ersten (und einzigen) Treffer.
    if (data && data.length > 0) {
        return data[0]; // z.B. { id: "uuid-1234", title: "API v3", ... }
    }
    // Wenn kein Node gefunden wurde, geben wir null zurück.
    return null;
};

/**
 * Ein Custom Hook, der die Logik für die Navigation über interne Links kapselt.
 * Er nutzt TanStack Query für den Datenabruf und React Router für die Navigation.
 */
export function useInternalLinkNavigation() {
    const navigate = useNavigate();
    const { vaultId } = useParams();
    const queryClient = useQueryClient();

    /**
     * Löst eine Suche nach dem Titel aus und navigiert bei Erfolg zum gefundenen Node.
     * @param {string} targetTitle - Der Titel des Nodes, zu dem navigiert werden soll.
     */
    const navigateToTitle = async (targetTitle) => {
        if (!vaultId || !targetTitle) {
            console.warn("Navigation abgebrochen: vaultId oder targetTitle fehlt.");
            return;
        }

        try {
            // Wir verwenden `fetchQuery`, um die Anfrage imperativ (auf Klick) auszuführen.
            // TanStack Query kümmert sich ums Caching.
            const node = await queryClient.fetchQuery({
                queryKey: ['nodeByTitle', vaultId, targetTitle],
                queryFn: () => fetchNodeByTitle(vaultId, targetTitle),
            });

            if (node && node.id) {
                console.log(`Node für "${targetTitle}" gefunden. Navigiere zu ID: ${node.id}`);
                // Navigation mit React Router zu der neuen URL.
                navigate(`/vaults/${vaultId}/nodes/${node.id}`);
            } else {
                console.warn(`Linkziel "${targetTitle}" konnte nicht gefunden werden.`);
                // Hier könnte man später eine "Toast"-Benachrichtigung anzeigen.
            }
        } catch (error) {
            console.error(`Fehler bei der Auflösung des Links für "${targetTitle}":`, error);
            // Hier könnte man eine Fehler-Benachrichtigung anzeigen.
        }
    };

    return { navigateToTitle };
}