// src/features/workspace/workspaceStore.js

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

const STORAGE_KEY = 'nexidion-workspace-state-v2';

export const useWorkspaceStore = create(
    persist(
        (set, get) => ({
            // ===============================================
            // STATE
            // ===============================================

            lastValidPaths: {},

            // Tree/selection state
            selectedNodeIds: new Set(),
            collapsedNodes: new Set(),
            savedSets: {},

            // UI layout
            activeContextTab: 'agent',
            breadcrumbPath: [],

            // Print Preview State (Not persisted)
            printPreviewData: null, // { nodes: [], toc: [] }

            // ===============================================
            // ACTIONS
            // ===============================================

            setLastValidPathForVault: (vaultId, path) => set(state => ({
                lastValidPaths: { ...state.lastValidPaths, [vaultId]: path },
            })),

            resetWorkspaceContext: () => set({
                lastValidPaths: get().lastValidPaths,
                selectedNodeIds: new Set(),
                collapsedNodes: new Set(),
                savedSets: {},
                breadcrumbPath: [],
            }),

            // UI layout
            setActiveContextTab: (tabKey) => set({ activeContextTab: tabKey }),
            setBreadcrumbPath: (path) => set({ breadcrumbPath: path }),

            // Tree/selection actions
            toggleNodeSelection: (nodeId) => set((state) => {
                const newSelection = new Set(state.selectedNodeIds);
                newSelection.has(nodeId) ? newSelection.delete(nodeId) : newSelection.add(nodeId);
                return { selectedNodeIds: newSelection };
            }),
            clearSelection: () => set({ selectedNodeIds: new Set() }),
            setSelection: (nodeIds) => set({ selectedNodeIds: new Set(nodeIds) }),

            toggleNodeCollapse: (nodeId) => set((state) => {
                const newCollapsed = new Set(state.collapsedNodes);
                newCollapsed.has(nodeId) ? newCollapsed.delete(nodeId) : newCollapsed.add(nodeId);
                return { collapsedNodes: newCollapsed };
            }),

            collapseAll: (allNodeIds) => set(() => ({
                collapsedNodes: new Set(allNodeIds),
            })),

            expandAll: () => set(() => ({
                collapsedNodes: new Set(),
            })),

            // Saved sets
            saveCurrentSet: (name) => {
                if (!name?.trim()) return;
                const currentSelection = get().selectedNodeIds;
                if (currentSelection.size === 0) return;
                set((state) => ({
                    savedSets: {
                        ...state.savedSets,
                        [name.trim()]: Array.from(currentSelection),
                    },
                }));
            },
            deleteSet: (name) => set((state) => {
                const newSets = { ...state.savedSets };
                delete newSets[name];
                return { savedSets: newSets };
            }),

            removeNodeFromContext: (nodeId) => set((state) => {
                const newSelection = new Set(state.selectedNodeIds);
                newSelection.delete(nodeId);
                const newCollapsed = new Set(state.collapsedNodes);
                newCollapsed.delete(nodeId);
                const newSavedSets = {};
                Object.entries(state.savedSets).forEach(([setName, idArray]) => {
                    const filtered = idArray.filter(id => id !== nodeId);
                    if (filtered.length > 0) newSavedSets[setName] = filtered;
                });
                return {
                    selectedNodeIds: newSelection,
                    collapsedNodes: newCollapsed,
                    savedSets: newSavedSets,
                };
            }),

            // Print Preview Actions
            openPrintPreview: (nodes, toc) => set({
                printPreviewData: { nodes, toc }
            }),
            closePrintPreview: () => set({
                printPreviewData: null
            }),
        }),
        {
            name: STORAGE_KEY,
            storage: createJSONStorage(() => localStorage, {
                replacer: (key, value) => {
                    if (value instanceof Set) {
                        return { __type: 'Set', value: [...value] };
                    }
                    return value;
                },
                reviver: (key, value) => {
                    if (value?.__type === 'Set') {
                        return new Set(value.value);
                    }
                    return value;
                },
            }),
            partialize: (state) => ({
                lastValidPaths: state.lastValidPaths,
                selectedNodeIds: state.selectedNodeIds,
                collapsedNodes: state.collapsedNodes,
                savedSets: state.savedSets,
                activeContextTab: state.activeContextTab,
                // printPreviewData is intentionally left out so it doesn't persist
            }),
        }
    )
);