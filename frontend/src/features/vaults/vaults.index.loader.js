import { redirect } from 'react-router-dom';
import apiClient from '../../api/apiClient';

export async function vaultIndexLoader({ params }) {
    console.log("[VAULT INDEX LOADER] Prüfe auf Umleitung...");
    try {
        // Wir brauchen die Baumdaten nur, um das Ziel zu finden.
        const treeData = await apiClient.get(`/api/vaults/${params.vaultId}/nodes?format=tree&v3=true`);

        if (treeData.data && treeData.data.length > 0) {
            const rootNode = treeData.data[0];
            console.log(`[VAULT INDEX LOADER] Leite um zu Wurzelknoten: ${rootNode.id}`);
            return redirect(`nodes/${rootNode.id}`); // Relative Umleitung ist sauberer
        }

        // Wenn der Vault leer ist, passiert nichts. Die VaultIndex-Komponente wird gerendert.
        console.log("[VAULT INDEX LOADER] Vault ist leer. Keine Umleitung.");
        return null;

    } catch (error) {
        console.error("Fehler im vaultIndexLoader:", error);
        return null;
    }
}