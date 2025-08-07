// src/features/workspace/workspaceStore.js

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

const STORAGE_KEY = 'nexidion-workspace-state-v1';

/**
 * Central state store for the entire workspace.
 * Manages UI state like selections, collapsed nodes, and the active chat session.
 * State is persisted to localStorage to maintain user context across sessions.
 */
export const useWorkspaceStore = create(
    persist(
        (set, get) => ({
            // ===============================================
            // === STATE PROPERTIES ===
            // ===============================================

            // --- Tree/Graph State ---
            selectedNodeIds: new Set(),
            collapsedNodes: new Set(),
            savedSets: {},

            // --- Diff State ---
            diffSelection: { base: null, compare: null },

            // --- LLM Model State ---
            chatModel: null,
            titleModel: null,

            // --- Active Chat Session State (Initialized for predictability) ---
            activeChatSessionId: null,
            activeChatTitle: 'New Chat',
            activeChatMessages: [], // Always initialize as an array

            // ===============================================
            // === ACTIONS ===
            // ===============================================

            // --- Workspace/Vault Actions ---
            resetWorkspaceContext: () => set({
                // Reset Tree/Graph state
                selectedNodeIds: new Set(),
                collapsedNodes: new Set(),
                savedSets: {},
                // Reset Diff state
                diffSelection: { base: null, compare: null },
                // Reset Active Chat Session state
                activeChatSessionId: null,
                activeChatTitle: 'New Chat',
                activeChatMessages: [],
            }),
            // --- LLM Actions ---

            setChatModel: (model) => set({ chatModel: model }),
            setTitleModel: (model) => set({ titleModel: model }),
            initializeModels: (availableModels) => {
                if (!availableModels || availableModels.length === 0) {
                    return;
                }
                const { chatModel, titleModel } = get();
                const needsUpdate = !chatModel || !titleModel;
                if (needsUpdate) {
                    set({
                        chatModel: chatModel || availableModels[0],
                        titleModel: titleModel || availableModels[0],
                    });
                }
            },


            // --- Chat Actions (Now simplified) ---
            startNewChat: () => set({
                activeChatSessionId: null,
                activeChatTitle: 'New Chat',
                activeChatMessages: []
            }),

            // Sets a complete session (e.g., after loading from history)
            setActiveChatSession: (sessionId, title, messages) => set({
                activeChatSessionId: sessionId,
                activeChatTitle: title || 'Chat',
                activeChatMessages: messages || [],
            }),

            // Appends a new message to the live buffer
            appendMessage: (message) => set(state => ({
                activeChatMessages: [...state.activeChatMessages, message]
            })),

            // Updates an existing message (e.g., from 'pending' to 'confirmed')
            updateMessage: (messageId, updates) => set(state => ({
                activeChatMessages: state.activeChatMessages.map(msg =>
                    msg.id === messageId ? { ...msg, ...updates } : msg
                )
            })),

            // Appends a token chunk to a streaming message
            appendChunkToMessage: (messageId, chunk) => set(state => ({
                activeChatMessages: state.activeChatMessages.map(msg =>
                    msg.id === messageId ? { ...msg, content: msg.content + chunk } : msg
                )
            })),

            setActiveChatTitle: (title) => set({ activeChatTitle: title }),

            // --- Diff Actions ---
            setDiffBase: (version) => set({ diffSelection: { base: version, compare: null } }),
            setDiffCompare: (version) => set(state => {
                // If the same compare item is clicked, deselect it.
                if (state.diffSelection.compare?.id === version?.id) {
                    return { diffSelection: { ...state.diffSelection, compare: null } };
                }
                return { diffSelection: { ...state.diffSelection, compare: version } };
            }),
            clearDiff: () => set({ diffSelection: { base: null, compare: null } }),

            // --- Tree Actions ---
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

            // --- Context Set Actions ---
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

            // --- Cleanup Action ---
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
            // === PERSISTENCE CONFIGURATION ===
            // ===============================================
            name: STORAGE_KEY,
            storage: createJSONStorage(() => localStorage, {
                // Custom replacer/reviver to handle Set objects, which JSON doesn't support natively.
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
            // Selectively persist only the parts of the state that make sense to restore.
            partialize: (state) => ({
                // UI State
                selectedNodeIds: state.selectedNodeIds,
                collapsedNodes: state.collapsedNodes,
                savedSets: state.savedSets,

                // Model Preferences
                chatModel: state.chatModel,
                titleModel: state.titleModel,

                // Active Chat Session (for better UX on refresh)
                activeChatSessionId: state.activeChatSessionId,
                activeChatTitle: state.activeChatTitle,
                activeChatMessages: state.activeChatMessages,
            }),
        }
    )
);