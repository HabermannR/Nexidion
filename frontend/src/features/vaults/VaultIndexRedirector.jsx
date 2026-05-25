// src/features/vaults/VaultIndexRedirector.jsx

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AppLoading from '../../components/AppLoading';

import { useVaultsQuery } from './hooks/useVaultsQuery.js';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery.js';

export default function VaultIndexRedirector() {
    const navigate = useNavigate();

    // Stage 1: load the vault list using the shared ETag-aware hook.
    // This is the same cache key+queryFn that AppShell uses, so no conflict.
    const { data: vaults, isSuccess: vaultsLoaded } = useVaultsQuery();

    const firstVaultId = vaults?.[0]?.id;

    // Stage 2: load the tree for the first vault once its ID is known.
    const { data: treeData, isSuccess: treeLoaded } = useVaultTreeQuery(firstVaultId);

    // Stage 3: redirect once both queries have settled.
    useEffect(() => {
        if (vaultsLoaded && vaults?.length === 0) {
            navigate('/settings/vaults', { replace: true });
            return;
        }

        if (vaultsLoaded && treeLoaded && treeData?.allNodesFlat) {
            const rootNode = treeData.allNodesFlat.find(node => node.parent_id === null);

            if (rootNode) {
                navigate(`/vaults/${firstVaultId}/nodes/${rootNode.id}`, { replace: true });
            } else {
                // Tree exists but has no root node — rare, fall back to vault root.
                navigate(`/vaults/${firstVaultId}`, { replace: true });
            }
        }
    }, [vaultsLoaded, treeLoaded, vaults, treeData, navigate, firstVaultId]);

    return <AppLoading />;
}
