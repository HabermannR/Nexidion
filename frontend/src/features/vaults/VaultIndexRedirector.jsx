// src/features/vaults/VaultIndexRedirector.jsx (Die neue, intelligente Version)

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';
import AppLoading from '../../components/AppLoading';

// V4: Wir importieren unseren neuen, dedizierten Hook für die Baumstruktur.
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery.js';

// Der Hook für die Vault-Liste bleibt derselbe.
const useVaultsQuery = () => {
    return useQuery({
        queryKey: ['allVaults'],
        queryFn: () => apiClient.get('/api/vaults/').then(res => res.data),
    });
};

export default function VaultIndexRedirector() {
    const navigate = useNavigate();

    // --- STUFE 1: Lade die Liste aller Vaults ---
    const { data: vaults, isSuccess: vaultsLoaded } = useVaultsQuery();

    // Wir merken uns die ID des ersten Vaults, sobald sie verfügbar ist.
    const firstVaultId = vaults?.[0]?.id;

    // --- STUFE 2: Lade den Baum für den ersten Vault, SOBALD seine ID bekannt ist ---
    const { data: treeData, isSuccess: treeLoaded } = useVaultTreeQuery(firstVaultId);

    // --- STUFE 3: Führe die Umleitung durch, SOBALD der Baum geladen ist ---
    useEffect(() => {
        // Diese Bedingung ist nur wahr, wenn BEIDE Abfragen erfolgreich waren.
        if (vaultsLoaded && treeLoaded && treeData) {
            // Finde den Wurzelknoten (den Node, der keine 'parent_id' hat).
            const rootNode = treeData.find(node => node.parent_id === null);

            if (rootNode) {
                // Ziel gefunden! Navigiere dorthin.
                console.log(`[VaultIndexRedirector] Leite zum Wurzelknoten ${rootNode.id} in Vault ${firstVaultId} um.`);
                navigate(`/vaults/${firstVaultId}/nodes/${rootNode.id}`, { replace: true });
            } else if (vaults.length > 0) {
                // Fallback: Baum ist da, aber kein Wurzelknoten? Dann nur zur Vault. Selten.
                console.warn(`[VaultIndexRedirector] Kein Wurzelknoten im Vault ${firstVaultId} gefunden. Leite nur zur Vault um.`);
                navigate(`/vaults/${firstVaultId}`, { replace: true });
            } else {
                // Fallback: Keine Vaults vorhanden.
                console.log('[VaultIndexRedirector] Keine Vaults gefunden, leite zu Settings um.');
                navigate('/settings/vaults', { replace: true });
            }
        } else if (vaultsLoaded && vaults?.length === 0) {
            // Spezialfall: Vault-Liste ist geladen und leer.
            console.log('[VaultIndexRedirector] Keine Vaults gefunden, leite zu Settings um.');
            navigate('/settings/vaults', { replace: true });
        }
    }, [vaultsLoaded, treeLoaded, vaults, treeData, navigate, firstVaultId]);

    // Zeige einen Ladebildschirm, während dieser mehrstufige Prozess läuft.
    return <AppLoading />;
}