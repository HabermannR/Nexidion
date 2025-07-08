// src/context/AppContext.jsx

import React, { createContext, useState, useContext, useCallback, useMemo, useEffect } from 'react';
import api from '../api/axios';
import { useAuth } from './AuthContext'; // Wichtig: Den AuthContext hier importieren
import qs from 'qs';

const AppContext = createContext(null);

export const useAppContext = () => useContext(AppContext);

export const AppProvider = ({ children }) => {
  // =======================================================
  // 1. ZUERST ALLE ZUSTANDSDEFINITIONEN (useState)
  // =======================================================
  const { isLoggedIn, isLoadingAuth } = useAuth();// Den Login-Status direkt im Context abfragen

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
  
  // Zustand: LLM-Modelle
  const [validModels, setValidModels] = useState([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [selectedModel, setSelectedModel] = useState(null);
  
  
  // =======================================================
  // 2. DANN ALLE FUNKTIONSDEFINITIONEN (useCallback)
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
    // Wir verwenden die Callback-Form von setActiveVault, um den vorherigen Wert zu bekommen.
    setActiveVault(prevActiveVault => {
        // Wir prüfen, ob es sich um einen ECHTEN Wechsel handelt:
        // Ein echter Wechsel liegt vor, wenn es einen vorherigen Vault gab
        // UND dessen ID sich von der neuen ID unterscheidet.
        const isActualChange = prevActiveVault && newVault && prevActiveVault.id !== newVault.id;

        if (isActualChange) {
            console.log("Vault-Wechsel erkannt. Setze Kontext zurück.");
            // Nur bei einem echten Wechsel setzen wir alles zurück.
            setGlobalTreeData([]);
            setSelectedNodeIds(new Set()); // Hier passiert der gezielte Reset.
            setChatHistory([]);
            setChatSessionId(null);
        }

        // Setze den neuen aktiven Vault und speichere ihn im localStorage.
        if (newVault) {
            localStorage.setItem('activeVaultId', newVault.id);
        } else {
            localStorage.removeItem('activeVaultId');
        }

        // Gib den neuen Vault zurück, um den State zu aktualisieren.
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
  }, []);;

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
      setChatHistory(sessionData.messages || []);
      setChatSessionId(sessionData.id);
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
      setChatHistory(prev => [...prev, message]);
  }, []);
  
  const appendStreamChunk = useCallback((chunk) => {
      setChatHistory(prev => {
          if (prev.length === 0) return prev;
          const newHistory = [...prev];
          const lastMessage = { ...newHistory[newHistory.length - 1] };
          lastMessage.content += chunk;
          newHistory[newHistory.length - 1] = lastMessage;
          return newHistory;
      });
  }, []);

  const changeSelectedModel = useCallback((modelId) => {
    setSelectedModel(modelId);
  }, []);
  
  // =======================================================
  // 3. ZULETZT ALLE SEITENEFFEKTE (useEffect)
  // =======================================================
  
  // Effekt für das initiale Laden der Daten und den Reset beim Logout
  useEffect(() => {
    if (isLoadingAuth) {
      return;
    }
    if (isLoggedIn) {
      fetchVaults();
      fetchModels();
    } else {
      setVaults([]);
      setActiveVault(null);
      setGlobalTreeData([]);
      setSelectedNodeIds(new Set()); // <-- Leert die Auswahl beim Logout
      setCollapsedNodes(new Set());
      setChatHistory([]);
      setChatSessionId(null);
      setValidModels([]);
      setSelectedModel(null);
      setIsPrintPreviewActive(false);
    }
  }, [isLoggedIn, isLoadingAuth, fetchVaults, fetchModels]);

  // Effekt zum Setzen des aktiven Vaults, nachdem die Liste geladen wurde
  useEffect(() => {
    if (vaults.length > 0 && !activeVault) {
      const lastVaultId = localStorage.getItem('activeVaultId');
      const lastVault = lastVaultId ? vaults.find(v => v.id === parseInt(lastVaultId)) : null;
      setActiveVault(lastVault || vaults[0]);
    }
  }, [vaults, activeVault]);

  // Effekt zum Setzen des aktiven Modells, nachdem die Liste geladen wurde
  useEffect(() => {
    if (validModels.length > 0 && !isLoadingModels) {
      const storedModelId = localStorage.getItem('selectedModel');
      const isStoredModelValid = validModels.some(m => m.id === storedModelId);
      setSelectedModel(isStoredModelValid ? storedModelId : validModels[0]?.id || null);
    }
  }, [validModels, isLoadingModels]);

  // Effekt zum Speichern des aktiven Modells bei Änderung
  useEffect(() => {
    if (selectedModel) {
      localStorage.setItem('selectedModel', selectedModel);
    }
  }, [selectedModel]);

  // Effekt zur Persistierung des Chats im Session-Storage
  useEffect(() => {
    try {
      const savedHistory = sessionStorage.getItem('chatHistory');
      const savedSessionId = sessionStorage.getItem('chatSessionId');
      if (savedHistory) setChatHistory(JSON.parse(savedHistory));
      if (savedSessionId) setChatSessionId(savedSessionId);
    } catch (error) {
      console.error("Failed to rehydrate chat state from sessionStorage", error);
      sessionStorage.clear();
    }
  }, []);

  useEffect(() => {
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
  }, [chatHistory, chatSessionId]);
  
  // 1. Effekt zum LADEN der Auswahl aus dem localStorage (Hydration)
  //    Läuft nur einmal, wenn der Context das erste Mal geladen wird.
  useEffect(() => {
    // Dieser Effekt sollte nur für den aktuellen Vault laden, aber da der
    // Vault-Wechsel die Auswahl sowieso zurücksetzt, können wir einen
    // globalen Key verwenden, der mit dem Vault-Wechsel überschrieben wird.
    // Ein Vault-spezifischer Key wäre `selectedNodeIds-${activeVault?.id}`.
    try {
      const storedIdsString = localStorage.getItem('selectedNodeIds');
      if (storedIdsString) {
        const storedIdsArray = JSON.parse(storedIdsString);
        // Stelle sicher, dass wir ein Array haben, bevor wir ein Set erstellen.
        if (Array.isArray(storedIdsArray)) {
            setSelectedNodeIds(new Set(storedIdsArray));
        }
      }
    } catch (error) {
      console.error("Failed to rehydrate node selection from localStorage", error);
      localStorage.removeItem('selectedNodeIds'); // Bereinige fehlerhafte Daten
    }
  }, []); // Die leere Abhängigkeitsliste `[]` sorgt dafür, dass dies nur einmal beim Mounten ausgeführt wird.


  // 2. Effekt zum SPEICHERN der Auswahl im localStorage (Persistenz)
  //    Läuft jedes Mal, wenn sich `selectedNodeIds` oder `activeVault` ändert.
  useEffect(() => {
    // Wir speichern nur, wenn ein Vault aktiv ist, um zu verhindern,
    // dass eine leere Auswahl beim Logout eine gültige Auswahl überschreibt.
    if (activeVault) {
        try {
          // Wandle das Set in ein Array um, da Sets nicht direkt als JSON gespeichert werden können.
          const idsToStore = Array.from(selectedNodeIds);
          localStorage.setItem('selectedNodeIds', JSON.stringify(idsToStore));
        } catch (error) {
          console.error("Failed to persist node selection to localStorage", error);
        }
    }
  }, [selectedNodeIds, activeVault]); // Die Abhängigkeit stellt sicher, dass bei jeder Änderung gespeichert wird.
  
  // =======================================================
  // 4. MEMOISIERUNG DES CONTEXT-WERTS UND RENDER
  // =======================================================
  const value = useMemo(() => ({
    // Zustandswerte
    selectedNodeIds,
    treeData: globalTreeData,
    isPrintPreviewActive,
    printPreviewData,
    collapsedNodes,
    vaults,
    activeVault,
    isLoadingVaults,
    chatHistory,
    chatSessionId,
    isChatLoading,
    validModels,
    isLoadingModels,
    selectedModel,
	clearNodeSelection,

    // Setter-Funktionen
    setSelectedNodeIds,
    setTreeDataForContext: setGlobalTreeData,
    setChatHistory,
    setChatSessionId,
    setIsChatLoading,
    
    // Stabilisierte Callback-Funktionen
    toggleNodeSelection,
    getContextContent,
    enterPrintPreview,
    exitPrintPreview,
    toggleNodeCollapse,
    fetchVaults,
    changeActiveVault,
    startNewChat,
    loadChatSession,
    appendMessage,
    appendStreamChunk,
    fetchModels,
    changeSelectedModel

  }), [
      // Alle Zustandswerte und stabilisierten Funktionen als Abhängigkeiten
      selectedNodeIds, globalTreeData, isPrintPreviewActive, printPreviewData,
      collapsedNodes, vaults, activeVault, isLoadingVaults, chatHistory,
      chatSessionId, isChatLoading, validModels, isLoadingModels, selectedModel,      
      toggleNodeSelection, getContextContent, enterPrintPreview, exitPrintPreview,
      toggleNodeCollapse, fetchVaults, changeActiveVault, startNewChat,
      loadChatSession, appendMessage, appendStreamChunk, fetchModels, changeSelectedModel,
	  clearNodeSelection
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};