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
            lastValidPaths: {},
            
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

            // --- UI Layout State ---
            activeContextTab: 'chat', // Standardwert
            breadcrumbPath: [],

            // ===============================================
            // === ACTIONS ===
            // ===============================================

            setLastValidPathForVault: (vaultId, path) => set(state => ({
                lastValidPaths: {
                    ...state.lastValidPaths,
                    [vaultId]: path,
                }
            })),

            // --- Workspace/Vault Actions ---
            resetWorkspaceContext: () => set({
                lastValidPaths: get().lastValidPaths, // Behalte die Pfade bei
                selectedNodeIds: new Set(),
                collapsedNodes: new Set(),
                savedSets: {},
                diffSelection: { base: null, compare: null },
                activeChatSessionId: null,
                activeChatTitle: 'New Chat',
                activeChatMessages: [],
                breadcrumbPath: [],
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

            // --- UI Layout Actions ---
            setActiveContextTab: (tabKey) => set({ activeContextTab: tabKey }),
            setBreadcrumbPath: (path) => set({ breadcrumbPath: path }),

            // --- Chat Actions (Now simplified) ---
            startNewChat: () => set({
                activeChatSessionId: null,
                activeChatTitle: 'New Chat',
                activeChatMessages: []
            }),

            setActiveChatSession: (sessionId, title, messages) => set({
                activeChatSessionId: sessionId,
                activeChatTitle: title || 'Chat',
                activeChatMessages: messages || [],
            }),

            appendMessage: (message) => set(state => ({
                activeChatMessages: [...state.activeChatMessages, message]
            })),

            updateMessage: (messageId, updates) => set(state => ({
                activeChatMessages: state.activeChatMessages.map(msg =>
                    msg.id === messageId ? { ...msg, ...updates } : msg
                )
            })),

            appendChunkToMessage: (messageId, chunk) => set(state => ({
                activeChatMessages: state.activeChatMessages.map(msg =>
                    msg.id === messageId ? { ...msg, content: msg.content + chunk } : msg
                )
            })),

            setActiveChatTitle: (title) => set({ activeChatTitle: title }),

            // --- Diff Actions ---
            setDiffBase: (version) => set(state => ({
                diffSelection: { ...state.diffSelection, base: version }
            })),

            setDiffCompare: (version) => set(state => {
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
            // KORREKTUR 2: HIER wird das große Objekt mit allen States und Actions geschlossen.
        }),
        {
            // ===============================================
            // === PERSISTENCE CONFIGURATION ===
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
                    if (value?.__type === 'Set') {
                        return new Set(value.value);
                    }
                    return value;
                },
            }),
            partialize: (state) => ({
                // UI State
                lastValidPaths: state.lastValidPaths,
                selectedNodeIds: state.selectedNodeIds,
                collapsedNodes: state.collapsedNodes,
                savedSets: state.savedSets,

                // Model Preferences
                chatModel: state.chatModel,
                titleModel: state.titleModel,

                // Active Chat Session
                activeChatSessionId: state.activeChatSessionId,
                activeChatTitle: state.activeChatTitle,
                activeChatMessages: state.activeChatMessages,

                activeContextTab: state.activeContextTab,

            }),
        }
    )
);