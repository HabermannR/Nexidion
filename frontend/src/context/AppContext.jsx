// src/context/AppContext.jsx

import React, { createContext, useState, useContext, useCallback, useMemo, useEffect, useRef } from 'react';
import api from '../api/axios';
import { useAuth } from './AuthContext';
import qs from 'qs';

const AppContext = createContext(null);

export const useAppContext = () => useContext(AppContext);

// src/context/AppContext.jsx

export const AppProvider = ({ children }) => {
  // =======================================================
  // 1. ZUSTANDSDEFINITIONEN
  // =======================================================
  const { isLoggedIn, isLoadingAuth } = useAuth();

  // Zustand: Nodes & Layout
  const [selectedNodeIds, setSelectedNodeIds] = useState(new Set());
  const [globalTreeData, setGlobalTreeData] = useState([]);
  const [isPrintPreviewActive, setIsPrintPreviewActive] = useState(false);
  const [printPreviewData, setPrintPreviewData] = useState({ nodes: [], toc: [] });
  const [collapsedNodes, setCollapsedNodes] = useState(new Set());
  
  // Zustand: Vaults
  const [vaults, setVaults] = useState([]);
  const [activeVault, setActiveVault] = useState(null);
  const [isLoadingVaults, setIsLoadingVaults] = useState(true);

  // Zustand: Globaler Chat
  const [chatHistory, setChatHistory] = useState([]);
  const [chatSessionId, setChatSessionId] = useState(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  
  // Zustand: LLM-Modelle & Lade-Logik
  const [validModels, setValidModels] = useState([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [selectedModel, setSelectedModel] = useState(null);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  
  // =======================================================
  // 2. CALLBACK-FUNKTIONEN
  // =======================================================

  // --- Datenlade-Funktionen ---
  const fetchVaults = useCallback(async () => {
    setIsLoadingVaults(true);
    try {
        const response = await api.get('/api/vaults');
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
      const response = await api.get('/api/llm/models');
      setValidModels(response.data || []);
    } catch (error) {
      console.error("Failed to fetch LLM models:", error);
      setValidModels([]);
    } finally {
      setIsLoadingModels(false);
    }
  }, []);

  // --- Vault-Management ---
  const changeActiveVault = useCallback((newVault) => {
    setActiveVault(prevActiveVault => {
        const isActualChange = prevActiveVault && newVault && prevActiveVault.id !== newVault.id;
        if (isActualChange) {
            console.log("Vault-Wechsel erkannt. Setze Kontext zurück.");
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

  // --- Node-Management ---
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
    if (selectedNodeIds.size === 0 || !activeVault) return { content: "", titles: [] };
    try {
      const response = await api.get('/api/nodes/content', {
        params: { vault_id: activeVault.id, node_ids: Array.from(selectedNodeIds) },
        paramsSerializer: params => qs.stringify(params, { arrayFormat: 'repeat' })
      });
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

  // --- Druckvorschau ---
  const enterPrintPreview = useCallback((data) => {
    setPrintPreviewData(data);
    setIsPrintPreviewActive(true);
  }, []);

  const exitPrintPreview = useCallback(() => {
    setIsPrintPreviewActive(false);
    setPrintPreviewData({ nodes: [], toc: [] });
  }, []);
  
  // --- Chat-Funktionen ---
  const startNewChat = useCallback(() => {
    setChatHistory([]);
    setChatSessionId(null);
    setIsChatLoading(false);
  }, []);

  const loadChatSession = useCallback(async (sessionIdToLoad) => {
    if (isChatLoading) return false;
    setIsChatLoading(true);
    try {
      const response = await api.get(`/api/chat/sessions/${sessionIdToLoad}`);
      const sessionData = response.data;
      if (activeVault && sessionData.vault_id !== activeVault.id) {
          alert("This chat session belongs to a different vault.");
          return false;
      }
      const messagesWithStrIds = (sessionData.messages || []).map(msg => ({
        ...msg,
        id: String(msg.id)
      }));
      setChatHistory(messagesWithStrIds);
      setChatSessionId(String(sessionData.id));
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
      const messageWithId = message.id ? message : { ...message, id: `temp-ui-${Date.now()}` };
      setChatHistory(prev => [...prev, messageWithId]);
  }, []);
  
  const updateMessageContent = useCallback((messageId, newContent) => {
    setChatHistory(prev => 
        prev.map(msg => 
            msg.id === messageId ? { ...msg, content: newContent } : msg
        )
    );
  }, []);
  
  const appendChunkToMessage = useCallback((chunk, targetId) => {
      setChatHistory(prev => {
          const messageIndex = prev.findIndex(msg => msg.id === targetId);
          if (messageIndex === -1) return prev; 
          const newHistory = [...prev];
          const updatedMessage = { 
              ...newHistory[messageIndex],
              content: newHistory[messageIndex].content + chunk
          };
          newHistory[messageIndex] = updatedMessage;
          return newHistory;
      });
  }, []);

  const replaceMessageId = useCallback((tempId, newId) => {
    setChatHistory(currentHistory =>
        currentHistory.map(msg =>
            msg.id === tempId ? { ...msg, id: newId } : msg
        )
    );
  }, []);

  const changeSelectedModel = useCallback((modelId) => {
    setSelectedModel(modelId);
  }, []);
  
  // =======================================================
  // 3. SEITENEFFEKTE (useEffect)
  // =======================================================
  
  // HOOK 1: Führt den initialen Ladevorgang aus, wenn der Benutzer eingeloggt ist.
  useEffect(() => {
    if (!isLoadingAuth && isLoggedIn && !initialLoadComplete) {
      console.log("Auth confirmed. Performing initial data load...");
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

  // HOOK 2: Bereinigt den Zustand, wenn der Benutzer sich ausloggt.
  useEffect(() => {
    if (!isLoadingAuth && !isLoggedIn) {
      console.log("User is logged out. Clearing all application state...");
      setVaults([]);
      setActiveVault(null);
      setGlobalTreeData([]);
      setSelectedNodeIds(new Set());
      setCollapsedNodes(new Set());
      setChatHistory([]);
      setChatSessionId(null);
      setValidModels([]);
      setSelectedModel(null);
      setIsPrintPreviewActive(false);
      sessionStorage.removeItem('chatHistory');
      sessionStorage.removeItem('chatSessionId');
      localStorage.removeItem('selectedNodeIds');
      localStorage.removeItem('activeVaultId');
      setInitialLoadComplete(false);
    }
  }, [isLoggedIn, isLoadingAuth]);

  // HOOK 3: Wählt einen Standard-Vault aus, nachdem die Vaults geladen wurden.
  useEffect(() => {
    if (vaults.length > 0 && !activeVault) {
      const lastVaultId = localStorage.getItem('activeVaultId');
      const lastVault = lastVaultId ? vaults.find(v => v.id === parseInt(lastVaultId, 10)) : null;
      setActiveVault(lastVault || vaults[0]);
    }
  }, [vaults, activeVault]);

  // HOOK 4: Wählt ein Standard-Modell aus, nachdem die Modelle geladen wurden.
  useEffect(() => {
    if (validModels.length > 0 && !isLoadingModels) {
      const storedModelId = localStorage.getItem('selectedModel');
      const isStoredModelValid = validModels.some(m => m.id === storedModelId);
      setSelectedModel(isStoredModelValid ? storedModelId : validModels[0]?.id || null);
    }
  }, [validModels, isLoadingModels]);

  // HOOK 5: Speichert das ausgewählte Modell im localStorage.
  useEffect(() => {
    if (selectedModel) {
      localStorage.setItem('selectedModel', selectedModel);
    }
  }, [selectedModel]);

  // HOOK 6: Speichert den Chat-Verlauf im sessionStorage.
  useEffect(() => {
    // Nicht speichern, bevor der initiale Ladevorgang abgeschlossen ist.
    if (!initialLoadComplete || isChatLoading) {
      return;
    }
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

  // HOOK 7: Speichert die Node-Auswahl im localStorage.
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
  // 4. MEMOISIERUNG DES CONTEXT-WERTS UND RENDER
  // =======================================================
  const value = useMemo(() => ({
    // ... (der value-Teil bleibt unverändert)
    selectedNodeIds, treeData: globalTreeData, isPrintPreviewActive, printPreviewData,
    collapsedNodes, vaults, activeVault, isLoadingVaults, chatHistory,
    chatSessionId, isChatLoading, validModels, isLoadingModels, selectedModel,      
    setSelectedNodeIds, setTreeDataForContext: setGlobalTreeData, setChatHistory,
    setChatSessionId, setIsChatLoading, clearNodeSelection, toggleNodeSelection,
    getContextContent, enterPrintPreview, exitPrintPreview, toggleNodeCollapse,
    fetchVaults, changeActiveVault, startNewChat, loadChatSession, appendMessage,
    appendChunkToMessage, updateMessageContent, replaceMessageId, fetchModels, changeSelectedModel
  }), [
      selectedNodeIds, globalTreeData, isPrintPreviewActive, printPreviewData,
      collapsedNodes, vaults, activeVault, isLoadingVaults, chatHistory,
      chatSessionId, isChatLoading, validModels, isLoadingModels, selectedModel,      
      clearNodeSelection, toggleNodeSelection, getContextContent, enterPrintPreview, exitPrintPreview,
      toggleNodeCollapse, fetchVaults, changeActiveVault, startNewChat,
      loadChatSession, appendMessage, appendChunkToMessage, updateMessageContent, replaceMessageId, fetchModels, changeSelectedModel
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};
