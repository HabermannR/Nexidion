// src/features/workspace/ContextBarContainer.jsx

import React, { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useWorkspaceStore } from './workspaceStore';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';
import ContextBarDisplay from './ContextBarDisplay.jsx';

export default function ContextBarContainer() {
    const { vaultId } = useParams();
    const [isExpanded, setIsExpanded] = useState(false);

    // 1. Daten vom Hook holen
    const { data: queryData } = useVaultTreeQuery(vaultId);

    // 2. Wichtige Daten stabil extrahieren
    const allNodesFlat = useMemo(() => queryData?.allNodesFlat || [], [queryData]);

    // 3. Daten aus dem Zustandsspeicher (zustand) holen
    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);

    const savedSets = useWorkspaceStore(state => state.savedSets);
    const clearSelection = useWorkspaceStore(state => state.clearSelection);
    const setSelection = useWorkspaceStore(state => state.setSelection);
    const saveCurrentSet = useWorkspaceStore(state => state.saveCurrentSet);
    const deleteSet = useWorkspaceStore(state => state.deleteSet);
    const selectionSize = selectedNodeIds.size;

    // Memoize die Liste der gespeicherten Sets für das Dropdown
    const savedSetsForDisplay = useMemo(() => {
        if (!savedSets || typeof savedSets !== 'object') return [];
        return Object.entries(savedSets).map(([name, ids]) => {
            if (!Array.isArray(ids)) {
                return { name, count: 0, ids: [] };
            }
            return { name, count: ids.length, ids };
        });
    }, [savedSets]);

    // 4. Titel für die ausgewählten IDs berechnen
    const selectedNodesWithTitles = useMemo(() => {
        if (allNodesFlat.length === 0 || selectedNodeIds.size === 0) {
            return [];
        }
        const nodeMap = new Map(allNodesFlat.map(node => [node.id, node]));
        const result = Array.from(selectedNodeIds)
            .map(id => {
                const node = nodeMap.get(id);
                return { id, title: node?.title || `ID ${id} nicht gefunden` };
                })
            .sort((a, b) => a.title.localeCompare(b.title));

        return result;

    }, [selectedNodeIds, allNodesFlat]);

    // 5. Alles an die "dumme" Anzeige-Komponente übergeben
    return (
        <ContextBarDisplay
            selectionSize={selectionSize}
            savedSets={savedSetsForDisplay}
            onClear={clearSelection}
            onSave={saveCurrentSet}
            onLoadSet={setSelection}
            onDeleteSet={deleteSet}
            isExpanded={isExpanded}
            onToggleExpand={() => setIsExpanded(prev => !prev)}
            selectedNodes={selectedNodesWithTitles}
        />
    );
}