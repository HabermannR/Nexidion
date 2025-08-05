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
            selectedNodeIds: new Set(),
            collapsedNodes: new Set(),
            savedSets: {},
            diffSelection: { base: null, compare: null },
            chatModel: null,
            titleModel: null,

            // ===============================================
            // === AKTIONEN ===
            // ===============================================

            // --- LLM-Aktionen ---
            setChatModel: (model) => set({ chatModel: model }),
            setTitleModel: (model) => set({ titleModel: model }),
            initializeModels: (availableModels) => set(state => {
                if (!availableModels || availableModels.length === 0) return {};
                return {
                    chatModel: state.chatModel || availableModels[0],
                    titleModel: state.titleModel || availableModels[0],
                };
            }),
            // ===============================================
            // NEU: Chat-Aktionen
            // ===============================================
            startNewChat: () => set({
                activeChatSessionId: null,
                activeChatTitle: 'New Chat',
                activeChatMessages: []
            }),

            // Setzt eine komplette Session (z.B. nach dem Laden aus der History)
            setActiveChatSession: (sessionId, title, messages) => set({
                activeChatSessionId: sessionId,
                activeChatTitle: title || 'Chat',
                activeChatMessages: messages || [],
            }),

            // Fügt eine neue Nachricht zum Live-Puffer hinzu
            appendMessage: (message) => set(state => {
                // ==========================================================
                // HIER IST DIE KORREKTUR
                // ==========================================================
                // Stelle sicher, dass state.activeChatMessages immer ein Array ist, bevor du den Spread-Operator verwendest.
                const currentMessages = Array.isArray(state.activeChatMessages) ? state.activeChatMessages : [];

                return {
                    activeChatMessages: [...currentMessages, message]
                };
            }),

            // Aktualisiert eine existierende Nachricht (z.B. von 'pending' zu 'confirmed')
            updateMessage: (messageId, updates) => set(state => {
                const currentMessages = Array.isArray(state.activeChatMessages) ? state.activeChatMessages : [];
                return {
                    activeChatMessages: currentMessages.map(msg =>
                        msg.id === messageId ? { ...msg, ...updates } : msg
                    )
                };
            }),

            // Fügt einen Token-Chunk zu einer streamenden Nachricht hinzu
            appendChunkToMessage: (messageId, chunk) => set(state => {
                const currentMessages = Array.isArray(state.activeChatMessages) ? state.activeChatMessages : [];
                return {
                    activeChatMessages: currentMessages.map(msg =>
                        msg.id === messageId ? { ...msg, content: msg.content + chunk } : msg
                    )
                };
            }),

            setActiveChatTitle: (title) => set({ activeChatTitle: title }),


            // --- Direkte Diff-Aktionen (vereinfacht) ---
            setDiffBase: (version) => set({ diffSelection: { base: version, compare: null } }),
            setDiffCompare: (version) => set(state => {
                // Wenn das gleiche Compare-Element geklickt wird, hebe die Auswahl auf.
                if (state.diffSelection.compare?.id === version?.id) {
                    return { diffSelection: { ...state.diffSelection, compare: null } };
                }
                return { diffSelection: { ...state.diffSelection, compare: version } };
            }),
            clearDiff: () => set({ diffSelection: { base: null, compare: null } }),

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
                // NEU: Auch die Modellauswahl persistieren, damit sie erhalten bleibt.
                chatModel: state.chatModel,
                titleModel: state.titleModel,
            }),
        }
    )
);