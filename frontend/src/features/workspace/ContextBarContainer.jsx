// src/features/workspace/left-panel/ContextBarContainer.jsx

import React, { useMemo } from 'react';
import { useWorkspaceStore } from './workspaceStore';
import ContextBarDisplay from './ContextBarDisplay.jsx';

/**
 * A "smart" container component that safely connects to the Zustand store.
 *
 * ARCHITECTURAL FIX:
 * This version uses multiple, small, "atomic" selectors. Each hook call returns
 * a single, stable value (a primitive or a direct object/function reference).
 * This respects React's core `useSyncExternalStore` rules and prevents re-render loops.
 *
 * The transformation logic (`Object.entries.map`) is then safely performed
 * inside `useMemo`, ensuring it only runs when its raw dependency (`savedSets`) changes.
 */
export default function ContextBarContainer() {
    // 1. Use multiple, atomic selectors. Each one is stable.
    const selectionSize = useWorkspaceStore(state => state.selectedNodeIds.size);
    const savedSets = useWorkspaceStore(state => state.savedSets);
    const clearSelection = useWorkspaceStore(state => state.clearSelection);
    const setSelection = useWorkspaceStore(state => state.setSelection);
    const saveCurrentSet = useWorkspaceStore(state => state.saveCurrentSet);
    const deleteSet = useWorkspaceStore(state => state.deleteSet);

    // 2. Perform the expensive/unstable transformation outside the selectors, wrapped in useMemo.
    // This code now ONLY runs if the raw `savedSets` object reference actually changes.
    const savedSetsForDisplay = useMemo(() => {
        // Defensive check for bad data
        if (!savedSets || typeof savedSets !== 'object') return [];

        return Object.entries(savedSets).map(([name, ids]) => {
            // Defensive check for corrupted entries
            if (!Array.isArray(ids)) {
                console.warn(`Data integrity issue: Saved set "${name}" has a non-array value.`, ids);
                return { name, count: 0, ids: [] };
            }
            return { name, count: ids.length, ids };
        });
    }, [savedSets]);

    // 3. Pass the safe, memoized data and actions down to the display component.
    return (
        <ContextBarDisplay
            selectionSize={selectionSize}
            savedSets={savedSetsForDisplay}
            onClear={clearSelection}
            onSave={saveCurrentSet}
            onLoadSet={setSelection}
            onDeleteSet={deleteSet}
        />
    );
}