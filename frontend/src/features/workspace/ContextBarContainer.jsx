// src/features/workspace/ContextBarContainer.jsx

import React, { useMemo, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useWorkspaceStore } from './workspaceStore';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';
import { copyContextContent } from '../../lib/clipboardService.js';
import apiClient from '../../api/apiClient.js';
import ContextBarDisplay from './ContextBarDisplay.jsx';

export default function ContextBarContainer() {
    const { vaultId } = useParams();
    const [isExpanded, setIsExpanded] = useState(false);
    const [copyStatus, setCopyStatus] = useState('idle'); // idle | copying | success | error

    const { data: queryData } = useVaultTreeQuery(vaultId);
    const allNodesFlat = useMemo(() => queryData?.allNodesFlat || [], [queryData]);

    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const clearSelection = useWorkspaceStore(state => state.clearSelection);
    const removeNodeFromContext = useWorkspaceStore(state => state.removeNodeFromContext);
    const selectionSize = selectedNodeIds.size;

    const selectedNodesWithTitles = useMemo(() => {
        if (allNodesFlat.length === 0 || selectedNodeIds.size === 0) return [];
        const nodeMap = new Map(allNodesFlat.map(node => [node.id, node]));
        return Array.from(selectedNodeIds)
            .map(id => ({ id, title: nodeMap.get(id)?.title || `ID ${id}` }))
            .sort((a, b) => a.title.localeCompare(b.title));
    }, [selectedNodeIds, allNodesFlat]);

    const handleCopyContent = useCallback(async () => {
        if (!vaultId || selectedNodeIds.size === 0) return;
        setCopyStatus('copying');

        const getContextContentForApi = async () => {
            const ids = Array.from(selectedNodeIds);
            try {
                const res = await apiClient.post(`/api/vaults/${vaultId}/nodes/content`, { node_ids: ids });
                return res.data;
            } catch (apiError) {
                throw new Error(apiError.response?.data?.error || 'Could not load node content.');
            }
        };

        try {
            await copyContextContent(getContextContentForApi);
            setCopyStatus('success');
            setTimeout(() => setCopyStatus('idle'), 2000);
        } catch {
            setCopyStatus('error');
            setTimeout(() => setCopyStatus('idle'), 3000);
        }
    }, [selectedNodeIds, vaultId]);

    return (
        <ContextBarDisplay
            selectionSize={selectionSize}
            onClear={clearSelection}
            onRemoveNode={removeNodeFromContext}
            isExpanded={isExpanded}
            onToggleExpand={() => setIsExpanded(prev => !prev)}
            selectedNodes={selectedNodesWithTitles}
            onCopyContent={handleCopyContent}
            copyStatus={copyStatus}
        />
    );
}
