// src/context/AppContext.js

import React, { createContext, useState, useContext, useCallback, useMemo } from 'react';
import api from '../api/axios';

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

  const enterPrintPreview = useCallback((data) => {
    setPrintPreviewData(data);
    setIsPrintPreviewActive(true);
  }, []);

  const exitPrintPreview = useCallback(() => {
    setIsPrintPreviewActive(false);
    setPrintPreviewData({ nodes: [], toc: [] });
  }, []);

  // useMemo ist hier großartig, um unnötige Re-Renders von Consumern zu vermeiden.
  const value = useMemo(() => ({
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

  }), [
      selectedNodeIds, 
      setSelectedNodeIds,
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
      setChatInputValue
    ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};