// src/features/workspace/ContextBarContainer.jsx

import React from 'react';
import { useMemo, useState } from 'react'; // Import useState
import { useWorkspaceStore } from './workspaceStore'; // Corrected path
import ContextBarDisplay from './ContextBarDisplay.jsx';

/**
 * A "smart" container that connects to the store and manages UI state.
 *
 * It now accepts a `nodes` prop, which should be an array of all available
 * node objects (e.g., [{id: '...', title: '...'}, ...]).
 * It uses this prop to look up the titles for the selected IDs.
 * It also manages the local "isExpanded" state for the detail view.
 */
export default function ContextBarContainer({ selectedNodes = [] }) {
    // 1. Local state to manage the expanded/collapsed view
    const [isExpanded, setIsExpanded] = useState(false);

    // 2. Use multiple, atomic selectors.
    // We need the full Set of IDs to derive the titles.
    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const savedSets = useWorkspaceStore(state => state.savedSets);
    const clearSelection = useWorkspaceStore(state => state.clearSelection);
    const setSelection = useWorkspaceStore(state => state.setSelection);
    const saveCurrentSet = useWorkspaceStore(state => state.saveCurrentSet);
    const deleteSet = useWorkspaceStore(state => state.deleteSet);

    // Derive selection size directly from the Set
    const selectionSize = selectedNodeIds.size;

    // 3. Perform expensive transformations in useMemo.

    // Memoize the list of saved sets for the dropdown
    const savedSetsForDisplay = useMemo(() => {
        if (!savedSets || typeof savedSets !== 'object') return [];
        return Object.entries(savedSets).map(([name, ids]) => {
            if (!Array.isArray(ids)) {
                console.warn(`Data integrity issue: Saved set "${name}" has a non-array value.`, ids);
                return { name, count: 0, ids: [] };
            }
            return { name, count: ids.length, ids };
        });
    }, [savedSets]);



    // 4. Pass everything down to the display component.
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
            selectedNodes={selectedNodes}
        />
    );
}