// src/context/AppContext.js

import React, { createContext, useState, useContext, useCallback, useMemo } from 'react';
import api from '../api/axios';

const AppContext = createContext(null);

export const useAppContext = () => useContext(AppContext);

export const AppProvider = ({ children }) => {
  const [selectedNodeIds, setSelectedNodeIds] = useState(new Set());
  const [globalTreeData, setGlobalTreeData] = useState([]);

  // --- MODIFIZIERT: State für die Druckvorschau ---
  // Wir speichern jetzt ein Objekt, das Nodes und das Inhaltsverzeichnis (toc) enthält.
  const [isPrintPreviewActive, setIsPrintPreviewActive] = useState(false);
  const [printPreviewData, setPrintPreviewData] = useState({ nodes: [], toc: [] });


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

  const getContextContent = useCallback(async () => {
    if (selectedNodeIds.size === 0) {
      return { content: "", titles: [] };
    }
    try {
      const response = await api.post('/api/nodes/content', {
        node_ids: Array.from(selectedNodeIds) 
      });
      return { content: response.data.content, titles: response.data.titles };
    } catch (error) {
      console.error("Failed to fetch context content:", error);
      alert("Could not fetch content for selected nodes.");
      return { content: "", titles: [] };
    }
  }, [selectedNodeIds]);

  // --- MODIFIZIERT: Funktionen zur Steuerung der Druckvorschau ---
  // enterPrintPreview erwartet jetzt ein Objekt: { nodes: [...], toc: [...] }
  const enterPrintPreview = useCallback((data) => {
    setPrintPreviewData(data);
    setIsPrintPreviewActive(true);
  }, []);

  const exitPrintPreview = useCallback(() => {
    setIsPrintPreviewActive(false);
    // Setzt den State auf den leeren Initialzustand zurück
    setPrintPreviewData({ nodes: [], toc: [] });
  }, []);

  const value = useMemo(() => ({
    selectedNodeIds,
    setSelectedNodeIds, // HINZUGEFÜGT: Die Setter-Funktion verfügbar machen
    toggleNodeSelection,
    getContextContent,
    treeData: globalTreeData,
    setTreeDataForContext: setGlobalTreeData,
    
    // --- MODIFIZIERT: Die neuen Werte für den Context verfügbar machen ---
    isPrintPreviewActive,
    printPreviewData, // Statt nodesToPrint
    enterPrintPreview,
    exitPrintPreview,

  }), [
      selectedNodeIds, 
      setSelectedNodeIds, // HINZUGEFÜGT: Als Abhängigkeit für useMemo
      toggleNodeSelection, 
      getContextContent, 
      globalTreeData, 
      // --- MODIFIZIERT: Abhängigkeiten für die neuen Werte hinzufügen ---
      isPrintPreviewActive,
      printPreviewData, // Statt nodesToPrint
      enterPrintPreview,
      exitPrintPreview
    ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};
