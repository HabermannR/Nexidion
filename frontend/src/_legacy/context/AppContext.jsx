// src/context/AppContext.jsx

import React, { createContext, useState, useContext, useCallback, useMemo, useEffect } from 'react';
import api from '../api/axios';
import { useAuth } from './AuthContext';

const AppContext = createContext(null);

export const useAppContext = () => useContext(AppContext);

export const AppProvider = ({ children }) => {
  // =======================================================
  // 1. STATE DEFINITIONS
  // =======================================================
  const { isLoggedIn, isLoadingAuth } = useAuth();

  // State: Nodes & Layout
  const [selectedNodeIds, setSelectedNodeIds] = useState(new Set());
  const [globalTreeData, setGlobalTreeData] = useState([]);
  const [isPrintPreviewActive, setIsPrintPreviewActive] = useState(false);
  const [printPreviewData, setPrintPreviewData] = useState({ nodes: [], toc: [] });
  const [collapsedNodes, setCollapsedNodes] = useState(new Set());

  // State: Vaults
  const [vaults, setVaults] = useState([]);
  const [activeVault, setActiveVault] = useState(null);
  const [isLoadingVaults, setIsLoadingVaults] = useState(true);

  // State: Global Chat
  const [chatHistory, setChatHistory] = useState([]);
  const [chatSessionId, setChatSessionId] = useState(null);
  const [activeSessionTitle, setActiveSessionTitle] = useState(null); // <-- NEUER STATE
  const [isChatLoading, setIsChatLoading] = useState(false);

  // State: LLM Models & Loading Logic
  const [validModels, setValidModels] = useState([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [selectedModel, setSelectedModel] = useState(null);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  // =======================================================
  // 2. CALLBACK FUNCTIONS
  // =======================================================

  // --- Data Fetching ---
  const fetchVaults = useCallback(async () => {
    setIsLoadingVaults(true);
    try {
      const response = await api.get('/api/vaults/');
      setVaults(response.data || []);
    } catch (error) {
      console.error("Failed to fetch vaults:", error);
      setVaults([]);
    } finally {
      setIsLoadingVaults(false);
    }
  }, []);

  const fetchModels = useCallback(async () => {
    setIsLoadingModels(true);
    try {
      const response = await api.get('/api/llm/models/');
      setValidModels(response.data || []);
    } catch (error) {
      console.error("Failed to fetch LLM models:", error);
      setValidModels([]);
    } finally {
      setIsLoadingModels(false);
    }
  }, []);

  // --- Vault Management ---
  const changeActiveVault = useCallback((newVault) => {
    setActiveVault(prevActiveVault => {
      const isActualChange = prevActiveVault && newVault && prevActiveVault.id !== newVault.id;
      if (isActualChange) {
        setGlobalTreeData([]);
        setSelectedNodeIds(new Set());
        setChatHistory([]);
        setChatSessionId(null);
      }
      if (newVault) {
        localStorage.setItem('activeVaultId', newVault.id);
      } else {
        localStorage.removeItem('activeVaultId');
      }
      return newVault;
    });
  }, []);

  // --- Node Management ---
  const toggleNodeCollapse = useCallback((nodeId) => {
    setCollapsedNodes(prevSet => {
      const newSet = new Set(prevSet);
      if (newSet.has(nodeId)) newSet.delete(nodeId);
      else newSet.add(nodeId);
      return newSet;
    });
  }, []);

  const toggleNodeSelection = useCallback((nodeId) => {
    setSelectedNodeIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) newSet.delete(nodeId);
      else newSet.add(nodeId);
      return newSet;
    });
  }, []);

  const getContextContent = useCallback(async () => {
    if (selectedNodeIds.size === 0 || !activeVault) {
      return { content: "", titles: [] };
    }
    try {
      const url = `/api/vaults/${activeVault.id}/nodes/content`;
      const payload = { node_ids: Array.from(selectedNodeIds) };
      const response = await api.post(url, payload);
      return response.data;
    } catch (error) {
      console.error("Failed to fetch context content:", error);
      alert(`Could not fetch content. Server responded with ${error.response?.status || 'error'}`);
      return { content: "", titles: [] };
    }
  }, [selectedNodeIds, activeVault]);

  // --- Tree ---
  const clearNodeSelection = useCallback(() => {
    setSelectedNodeIds(new Set());
  }, []);

  // --- Print Preview ---
  const enterPrintPreview = useCallback((data) => {
    setPrintPreviewData(data);
    setIsPrintPreviewActive(true);
  }, []);

  const exitPrintPreview = useCallback(() => {
    setIsPrintPreviewActive(false);
    setPrintPreviewData({ nodes: [], toc: [] });
  }, []);

  // --- Chat Functions (fokussiert auf State-Management) ---
  const startNewChat = useCallback(() => {
    setChatHistory([]);
    setChatSessionId(null);
    setActiveSessionTitle(null);
    setIsChatLoading(false);
  }, []);

  const loadChatSession = useCallback(async (sessionIdToLoad) => {
    if (isChatLoading || !activeVault) return false;

    setIsChatLoading(true);
    try {
      const response = await api.get(`/api/vaults/${activeVault.id}/sessions/${sessionIdToLoad}`);
      const sessionData = response.data;

      const messagesWithStrIds = (sessionData.messages || []).map(msg => ({
        ...msg,
        id: String(msg.id)
      }));
      setChatHistory(messagesWithStrIds);
      setChatSessionId(String(sessionData.id));
      setActiveSessionTitle(sessionData.title);
      return true;
    } catch (error) {
      console.error("Failed to load session history:", error);
      alert("Could not load the selected session.");
      return false;
    } finally {
      setIsChatLoading(false);
    }
  }, [activeVault, isChatLoading]);

    const appendMessage = useCallback((message) => {
    // Fügt eine neue Nachricht hinzu UND sortiert das gesamte Array danach.
    setChatHistory(prev => {
      const newHistory = [...prev, message];
      // Temporäre Nachrichten ohne sort_order werden ans Ende sortiert.
      return newHistory.sort((a, b) => (a.sort_order || Infinity) - (b.sort_order || Infinity));
    });
  }, []);

  const updateMessage = useCallback((messageId, updates) => {
    // Aktualisiert eine Nachricht UND sortiert das gesamte Array danach.
    // Das ist entscheidend, wenn die finale `sort_order` vom Server kommt.
    setChatHistory(prev => {
      const newHistory = prev.map(msg =>
          msg.id === messageId ? { ...msg, ...updates, id: updates.id || msg.id } : msg
      );
      return newHistory.sort((a, b) => (a.sort_order || Infinity) - (b.sort_order || Infinity));
    });
  }, []);

  const appendChunkToMessage = useCallback((messageId, chunk) => {
    setChatHistory(prev =>
        prev.map(msg =>
            msg.id === messageId
                ? { ...msg, content: msg.content + chunk }
                : msg
        )
    );
  }, []);

  const changeSelectedModel = useCallback((modelId) => {
    setSelectedModel(modelId);
  }, []);

  // =======================================================
  // 3. SIDE EFFECTS (useEffect)
  // =======================================================

  // HOOK 1: Initial data load on login.
  useEffect(() => {
    if (!isLoadingAuth && isLoggedIn && !initialLoadComplete) {
      fetchVaults();
      fetchModels();
      try {
        const savedHistory = sessionStorage.getItem('chatHistory');
        const savedSessionId = sessionStorage.getItem('chatSessionId');
        if (savedHistory) {
          const parsedHistory = JSON.parse(savedHistory);
          const historyWithStrIds = parsedHistory.map(msg => ({ ...msg, id: String(msg.id) }));
          setChatHistory(historyWithStrIds);
        }
        if (savedSessionId) setChatSessionId(savedSessionId);

        const storedIdsString = localStorage.getItem('selectedNodeIds');
        if (storedIdsString) {
          const storedIdsArray = JSON.parse(storedIdsString);
          if (Array.isArray(storedIdsArray)) setSelectedNodeIds(new Set(storedIdsArray));
        }
      } catch (error) {
        console.error("Failed to rehydrate state from storage", error);
        sessionStorage.clear();
      }
      setInitialLoadComplete(true);
    }
  }, [isLoggedIn, isLoadingAuth, initialLoadComplete, fetchVaults, fetchModels]);

  // HOOK 2: State cleanup on logout.
  useEffect(() => {
    if (!isLoadingAuth && !isLoggedIn) {
      console.log("User is logged out. Clearing all application state...");
      setVaults([]); setActiveVault(null); setGlobalTreeData([]);
      setSelectedNodeIds(new Set()); setCollapsedNodes(new Set());
      setChatHistory([]); setChatSessionId(null);
      setValidModels([]); setSelectedModel(null);
      setIsPrintPreviewActive(false);
      sessionStorage.removeItem('chatHistory');
      sessionStorage.removeItem('chatSessionId');
      localStorage.removeItem('selectedNodeIds');
      localStorage.removeItem('activeVaultId');
      setInitialLoadComplete(false);
    }
  }, [isLoggedIn, isLoadingAuth]);

  // HOOK 3: Set default vault after vaults load.
  useEffect(() => {
    if (vaults.length > 0 && !activeVault) {
      const lastVaultId = localStorage.getItem('activeVaultId');
      const lastVault = lastVaultId ? vaults.find(v => v.id === parseInt(lastVaultId, 10)) : null;
      setActiveVault(lastVault || vaults[0]);
    }
  }, [vaults, activeVault]);

  // HOOK 4: Set default model after models load.
  useEffect(() => {
    if (validModels.length > 0 && !isLoadingModels) {
      const storedModelId = localStorage.getItem('selectedModel');
      const isStoredModelValid = validModels.some(m => m.id === storedModelId);
      setSelectedModel(isStoredModelValid ? storedModelId : validModels[0]?.id || null);
    }
  }, [validModels, isLoadingModels]);

  // HOOK 5: Persist selected model.
  useEffect(() => {
    if (selectedModel) {
      localStorage.setItem('selectedModel', selectedModel);
    }
  }, [selectedModel]);

  // HOOK 6: Persist chat history.
  useEffect(() => {
    if (!initialLoadComplete || isChatLoading) return;
    try {
      sessionStorage.setItem('chatHistory', JSON.stringify(chatHistory));
      if (chatSessionId) {
        sessionStorage.setItem('chatSessionId', chatSessionId);
      } else {
        sessionStorage.removeItem('chatSessionId');
      }
    } catch (error) {
      console.error("Failed to persist chat state to sessionStorage", error);
    }
  }, [chatHistory, chatSessionId, isChatLoading, initialLoadComplete]);

  // HOOK 7: Persist node selection.
  useEffect(() => {
    if (activeVault) {
      try {
        const idsToStore = Array.from(selectedNodeIds);
        localStorage.setItem('selectedNodeIds', JSON.stringify(idsToStore));
      } catch (error) {
        console.error("Failed to persist node selection to localStorage", error);
      }
    }
  }, [selectedNodeIds, activeVault]);

  // =======================================================
  // 4. MEMOIZED CONTEXT VALUE AND RENDER
  // =======================================================
  const value = useMemo(() => ({
    // State
    selectedNodeIds, treeData: globalTreeData, isPrintPreviewActive, printPreviewData,
    collapsedNodes, vaults, activeVault, isLoadingVaults, chatHistory,
    chatSessionId, isChatLoading, validModels, isLoadingModels, selectedModel,
    // Setters & Functions
    setSelectedNodeIds, setTreeDataForContext: setGlobalTreeData, setChatHistory,
    setChatSessionId, setIsChatLoading, clearNodeSelection, toggleNodeSelection,
    getContextContent, enterPrintPreview, exitPrintPreview, toggleNodeCollapse,
    fetchVaults, changeActiveVault, startNewChat, loadChatSession,
    // Fokussierte Chat-Update-Funktionen
    appendMessage,
    updateMessage,
    appendChunkToMessage,
    activeSessionTitle, setActiveSessionTitle,
    fetchModels, changeSelectedModel,
    api,
  }), [
    // Alle State-Werte
    selectedNodeIds, globalTreeData, isPrintPreviewActive, printPreviewData,
    collapsedNodes, vaults, activeVault, isLoadingVaults, chatHistory,
    chatSessionId, isChatLoading, validModels, isLoadingModels, selectedModel,
    // Alle Callback-Funktionen
    clearNodeSelection, toggleNodeSelection, getContextContent, enterPrintPreview, exitPrintPreview,
    toggleNodeCollapse, fetchVaults, changeActiveVault, startNewChat,
    loadChatSession, appendMessage, updateMessage, appendChunkToMessage,
    activeSessionTitle, setActiveSessionTitle, fetchModels, changeSelectedModel,
    api,
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};