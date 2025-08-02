// src/context/contextStore.js
import {create} from 'zustand';
import {persist, createJSONStorage} from 'zustand/middleware';

// Der Zustandsschlüssel für den Local Storage
const STORAGE_KEY = 'nexidion-ui-state';

export const useContextStore = create(
    // 1. Wir wickeln unseren Store in die `persist`-Middleware ein.
    persist(
        (set, get) => ({
            // === ZUSTAND (State) ===
            // Die Anfangswerte. `persist` wird sie sofort mit den gespeicherten Werten überschreiben, falls vorhanden.
            selectedNodeIds: new Set(),
            collapsedNodes: new Set(),
            savedSets: {}, // Gespeicherte Auswahl-Sets

            // === AKTIONEN (Actions) ===
            // Die Aktionen sind jetzt wieder super einfach. Die Middleware kümmert sich ums Speichern.

            // --- Node-Auswahl ---
            toggleNodeSelection: (nodeId) =>
                set((state) => {
                    const newSelection = new Set(state.selectedNodeIds);
                    newSelection.has(nodeId) ? newSelection.delete(nodeId) : newSelection.add(nodeId);
                    return {selectedNodeIds: newSelection};
                }),

            clearSelection: () => set({selectedNodeIds: new Set()}),

            setSelection: (nodeIds) => set({selectedNodeIds: new Set(nodeIds)}),

            // --- Node-Kollaps-Zustand ---
            toggleNodeCollapse: (nodeId) =>
                set((state) => {
                    const newCollapsed = new Set(state.collapsedNodes);
                    newCollapsed.has(nodeId) ? newCollapsed.delete(nodeId) : newCollapsed.add(nodeId);
                    return {collapsedNodes: newCollapsed};
                }),

            // --- Kontext-Set-Verwaltung ---
            saveCurrentSet: (name) => {
                if (!name || !name.trim()) return;
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
                    const newSets = {...state.savedSets};
                    delete newSets[name];
                    return {savedSets: newSets};
                });
            },
        }),
        {
            // 2. Konfiguration für die Middleware
            name: STORAGE_KEY, // Der Key für den localStorage
            storage: createJSONStorage(() => localStorage, {
                // 3. Wir bringen `persist` bei, wie man `Set`-Objekte behandelt
                replacer: (key, value) => {
                    if (value instanceof Set) {
                        // Wandle Sets beim Speichern in Arrays um
                        return {__type: 'Set', value: [...value]};
                    }
                    return value;
                },
                reviver: (key, value) => {
                    if (value && value.__type === 'Set') {
                        // Wandle Arrays beim Laden zurück in Sets
                        return new Set(value.value);
                    }
                    return value;
                },
            }),
        }
    )
);