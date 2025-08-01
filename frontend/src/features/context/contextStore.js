// src/context/contextStore.js
import { create } from 'zustand';

const STORAGE_KEY = 'nexidion_context_sets'; // Wiederverwendbarer Key

// Helper-Funktion, um die Sets aus dem localStorage zu laden
const loadSetsFromStorage = () => {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored ? JSON.parse(stored) : {};
    } catch (error) {
        console.error("Fehler beim Laden der Kontext-Sets:", error);
        return {};
    }
};

export const useContextStore  = create((set, get) => ({
    // === ZUSTAND (State) ===
    selectedNodeIds: new Set(),
    collapsedNodes: new Set(),
    savedSets: loadSetsFromStorage(),

    // === AKTIONEN (Actions) ===

    // --- Node-Auswahl ---
    toggleNodeSelection: (nodeId) => set((state) => {
        const newSelection = new Set(state.selectedNodeIds);
        if (newSelection.has(nodeId)) {
            newSelection.delete(nodeId);
        } else {
            newSelection.add(nodeId);
        }
        return { selectedNodeIds: newSelection };
    }),

    clearSelection: () => set({ selectedNodeIds: new Set() }),

    setSelection: (nodeIds) => set({ selectedNodeIds: new Set(nodeIds) }),

    // --- Node-Kollaps-Zustand ---
    toggleNodeCollapse: (nodeId) => set((state) => {
        const newCollapsed = new Set(state.collapsedNodes);
        if (newCollapsed.has(nodeId)) {
            newCollapsed.delete(nodeId);
        } else {
            newCollapsed.add(nodeId);
        }
        return { collapsedNodes: newCollapsed };
    }),

    // --- Kontext-Set-Verwaltung (Speichern/Laden/Löschen) ---
    saveCurrentSet: (name) => {
        if (!name || !name.trim()) return;
        const currentSelection = get().selectedNodeIds;
        if (currentSelection.size === 0) return;

        const newSets = {
            ...get().savedSets,
            [name.trim()]: Array.from(currentSelection)
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(newSets));
        set({ savedSets: newSets });
    },

    deleteSet: (name) => {
        const newSets = { ...get().savedSets };
        delete newSets[name];
        localStorage.setItem(STORAGE_KEY, JSON.stringify(newSets));
        set({ savedSets: newSets });
    },
}));