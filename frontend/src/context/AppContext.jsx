// src/context/AppContext.js

import React, { createContext, useState, useContext, useCallback, useMemo } from 'react';
import api from '../api/axios';
import qs from 'qs'; // Oben in der Datei importieren

const AppContext = createContext(null);

export const useAppContext = () => useContext(AppContext);

export const AppProvider = ({ children }) => {
  // Bestehender State
  const [selectedNodeIds, setSelectedNodeIds] = useState(new Set());
  const [globalTreeData, setGlobalTreeData] = useState([]);
  const [isPrintPreviewActive, setIsPrintPreviewActive] = useState(false);
  const [printPreviewData, setPrintPreviewData] = useState({ nodes: [], toc: [] });
  const [collapsedNodes, setCollapsedNodes] = useState(new Set());
  const [chatInputValue, setChatInputValue] = useState('');
  const [vaults, setVaults] = useState([]);
  const [activeVault, setActiveVault] = useState(null);
  const [isLoadingVaults, setIsLoadingVaults] = useState(true);

  const toggleNodeCollapse = useCallback((nodeId) => {
    setCollapsedNodes(prevSet => {
      const newSet = new Set(prevSet);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  }, []); // Keine Abhängigkeiten, da nur der Setter von useState verwendet wird
  // ===================================================================

  // Bestehende Funktionen
  const toggleNodeSelection = useCallback((nodeId) => {
    setSelectedNodeIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  }, []);

  // KORREKTE, REPARIERTE VERSION für AppContext.jsx

const getContextContent = useCallback(async () => {
  // 1. Wenn keine Nodes ausgewählt sind, passiert nichts. Das ist korrekt.
  if (selectedNodeIds.size === 0) {
    return { content: "", titles: [] };
  }

  // 2. Wenn kein Vault aktiv ist (sollte nicht passieren, aber sicher ist sicher), auch nichts tun.
  if (!activeVault) {
      console.warn("getContextContent called without an active vault.");
      return { content: "", titles: [] };
  }

  try {
    // 3. Wandle das Set der IDs in ein normales Array um.
    const nodeIds = Array.from(selectedNodeIds);

    // 4. DER ENTSCHEIDENDE FIX:
    //    - Wir verwenden `api.get`, nicht `api.post`.
    //    - Wir übergeben die Daten als `params`-Objekt. Axios wandelt dies
    //      automatisch in einen URL-Query-String um.
    //      z.B.: /api/nodes/content?vault_id=1&node_ids=5&node_ids=12
    const response = await api.get('/api/nodes/content', {
	  params: {
		vault_id: activeVault.id,
		node_ids: nodeIds
	  },
	  // Füge diesen paramsSerializer hinzu
	  paramsSerializer: params => {
		return qs.stringify(params, { arrayFormat: 'repeat' });
	  }
	});
    
    // 5. Gib die vom Backend erhaltenen Daten zurück.
    return { content: response.data.content, titles: response.data.titles };

  } catch (error) {
    console.error("Failed to fetch context content:", error);
    // Gib eine klarere Fehlermeldung aus, die dem Benutzer hilft.
    let errorMessage = "Could not fetch content for selected nodes.";
    if (error.response) {
      // z.B. "(Server responded with 404)"
      errorMessage += ` (Server responded with ${error.response.status})`;
    }
    alert(errorMessage);
    return { content: "", titles: [] };
  }
}, [selectedNodeIds, activeVault]); // Die Abhängigkeiten sind korrekt.

  const enterPrintPreview = useCallback((data) => {
    setPrintPreviewData(data);
    setIsPrintPreviewActive(true);
  }, []);

  const exitPrintPreview = useCallback(() => {
    setIsPrintPreviewActive(false);
    setPrintPreviewData({ nodes: [], toc: [] });
  }, []);
  
   const fetchVaults = useCallback(async () => {
    setIsLoadingVaults(true);
    try {
        const response = await api.get('/api/vaults');
        const loadedVaults = response.data || [];
        setVaults(loadedVaults);

        const lastVaultId = localStorage.getItem('activeVaultId');
        // `find` gibt `undefined` zurück, wenn nichts gefunden wird, was `||` korrekt behandelt
        const lastVault = loadedVaults.find(v => v.id === parseInt(lastVaultId));
        
        // Setze den aktiven Vault: gespeicherter Vault ODER der erste ODER null
        const newActiveVault = lastVault || loadedVaults[0] || null;
        setActiveVault(newActiveVault);

        // Speichere auch die ID im localStorage, falls der erste Vault als Fallback gewählt wurde
        if (newActiveVault) {
            localStorage.setItem('activeVaultId', newActiveVault.id);
        } else {
            localStorage.removeItem('activeVaultId');
        }

    } catch (error) {
        console.error("Failed to fetch vaults:", error);
        setVaults([]);
        setActiveVault(null);
    } finally {
        setIsLoadingVaults(false);
    }
  }, []); // Keine Abhängigkeiten, da die Funktion in sich abgeschlossen ist

  const changeActiveVault = useCallback((vault) => {
    setActiveVault(vault);
    if (vault) {
        localStorage.setItem('activeVaultId', vault.id);
    } else {
        localStorage.removeItem('activeVaultId');
    }
    // Wichtig: Wenn der Vault gewechselt wird, müssen Baum und ausgewählte Nodes zurückgesetzt werden
    setGlobalTreeData([]);
    setSelectedNodeIds(new Set());
  }, []);

  // useMemo ist hier großartig, um unnötige Re-Renders von Consumern zu vermeiden.
  const value = useMemo(() => ({
    // Bestehende Werte
    selectedNodeIds,
    setSelectedNodeIds,
    toggleNodeSelection,
    getContextContent,
    treeData: globalTreeData,
    setTreeDataForContext: setGlobalTreeData,
    isPrintPreviewActive,
    printPreviewData,
    enterPrintPreview,
    exitPrintPreview,
    collapsedNodes,
    toggleNodeCollapse,
	chatInputValue,
    setChatInputValue,

    // ========================================================================
    // VAULT-FIX: Neue Werte und Funktionen hinzufügen
    // ========================================================================
    vaults,
    activeVault,
    isLoadingVaults,
    fetchVaults,
    changeActiveVault

  }), [
      // Bestehende Abhängigkeiten
      selectedNodeIds, 
      toggleNodeSelection, 
      getContextContent, 
      globalTreeData, 
      isPrintPreviewActive,
      printPreviewData,
      enterPrintPreview,
      exitPrintPreview,
      collapsedNodes,
      toggleNodeCollapse,
	  chatInputValue,

      // VAULT-FIX: Neue Abhängigkeiten
      vaults,
      activeVault,
      isLoadingVaults,
      fetchVaults,
      changeActiveVault
    ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};