// src/features/workspace/workspaceStore.js

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

const STORAGE_KEY = 'nexidion-workspace-state-v1';

/**
 * RADIKALE VEREINFACHUNG: Zentraler Zustandsspeicher für den Arbeitsbereich.
 * Keine komplexe Mutation-Detection, keine Race Conditions.
 * Einfache Regel: URL-Parameter bestimmen, was angezeigt wird.
 */
export const useWorkspaceStore = create(
    persist(
        (set, get) => ({
            // ===============================================
            // === ZUSTAND ===
            // ===============================================

            // --- Linkes Panel & Baum (wird persistiert) ---
            selectedNodeIds: new Set(),
            collapsedNodes: new Set(),
            savedSets: {},

            // --- Versionsauswahl (nicht persistiert) ---
            activeNodeVersions: [],
            diffSelection: { base: null, compare: null },

            // ===============================================
            // === AKTIONEN ===
            // ===============================================

            setActiveNodeVersions: (versions) => {
                const current = get().activeNodeVersions;

                // Einfacher Vergleich - nur updaten wenn sich was geändert hat
                if (JSON.stringify(current) !== JSON.stringify(versions)) {
                    console.log(`[STORE] Neue Versionen erhalten (${versions?.length || 0} Stück)`);
                    set({ activeNodeVersions: versions || [] });
                }
            },

            /**
             * SIMPLE LOGIK: URL-Parameter bestimmen die Anzeige
             * - versionNumber = null → neueste Version (Index 0)
             * - versionNumber = "5" → Version 5
             * - compareNumber = "3" → Version 3 zum Vergleich
             */
            syncDiffSelectionFromUrl: (versionNumber, compareNumber) => {
                const { activeNodeVersions } = get();

                console.log(`[STORE] Sync: version=${versionNumber}, compare=${compareNumber}`);

                if (!activeNodeVersions || activeNodeVersions.length === 0) {
                    console.log('[STORE] Keine Versionen verfügbar');
                    set({ diffSelection: { base: null, compare: null } });
                    return;
                }

                // SIMPLE REGEL: null = neueste (Index 0), sonst suche die Version
                const base = versionNumber === null
                    ? activeNodeVersions[0]  // Neueste Version nach Mutation
                    : activeNodeVersions.find(v => String(v.version) === versionNumber);

                const compare = compareNumber
                    ? activeNodeVersions.find(v => String(v.version) === compareNumber)
                    : null;

                console.log(`[STORE] Setze Auswahl: ${base ? `v${base.version}` : 'null'}${compare ? ` vs v${compare.version}` : ''}`);

                // Immer setzen - React wird nur re-rendern wenn sich was geändert hat
                set({ diffSelection: { base, compare } });
            },

            // --- Baum-Aktionen ---
            toggleNodeSelection: (nodeId) =>
                set((state) => {
                    const newSelection = new Set(state.selectedNodeIds);
                    newSelection.has(nodeId) ? newSelection.delete(nodeId) : newSelection.add(nodeId);
                    return { selectedNodeIds: newSelection };
                }),

            clearSelection: () => set({ selectedNodeIds: new Set() }),

            setSelection: (nodeIds) => set({ selectedNodeIds: new Set(nodeIds) }),

            toggleNodeCollapse: (nodeId) =>
                set((state) => {
                    const newCollapsed = new Set(state.collapsedNodes);
                    newCollapsed.has(nodeId) ? newCollapsed.delete(nodeId) : newCollapsed.add(nodeId);
                    return { collapsedNodes: newCollapsed };
                }),

            // --- Kontext-Sets ---
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

            deleteSet: (name) => {
                set((state) => {
                    const newSets = { ...state.savedSets };
                    delete newSets[name];
                    return { savedSets: newSets };
                });
            },

            // --- Direkte Diff-Aktionen ---
            setDiffSelection: (selection) => {
                set({ diffSelection: selection });
            },

            clearDiffSelection: () => {
                set({ diffSelection: { base: null, compare: null } });
            },

            // --- Aufräumen ---
            removeNodeFromContext: (nodeId) => {
                set((state) => {
                    const newSelection = new Set(state.selectedNodeIds);
                    newSelection.delete(nodeId);

                    const newCollapsed = new Set(state.collapsedNodes);
                    newCollapsed.delete(nodeId);

                    const newSavedSets = {};
                    Object.entries(state.savedSets).forEach(([setName, idArray]) => {
                        const filteredIds = idArray.filter(id => id !== nodeId);
                        if (filteredIds.length > 0) {
                            newSavedSets[setName] = filteredIds;
                        }
                    });

                    return {
                        selectedNodeIds: newSelection,
                        collapsedNodes: newCollapsed,
                        savedSets: newSavedSets,
                    };
                });
            },
        }),
        {
            // ===============================================
            // === PERSISTIERUNG ===
            // ===============================================
            name: STORAGE_KEY,
            storage: createJSONStorage(() => localStorage, {
                replacer: (key, value) => {
                    if (value instanceof Set) {
                        return { __type: 'Set', value: [...value] };
                    }
                    return value;
                },
                reviver: (key, value) => {
                    if (value?.__type === 'Set') {  // ← Zwei Punkte, nicht drei!
                        return new Set(value.value);
                    }
                    return value;
                },
            }),
            // Nur UI-Zustände persistieren, nicht die Versionsauswahl
            partialize: (state) => ({
                selectedNodeIds: state.selectedNodeIds,
                collapsedNodes: state.collapsedNodes,
                savedSets: state.savedSets,
            }),
        }
    )
);