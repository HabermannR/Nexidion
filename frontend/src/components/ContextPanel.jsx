// src/components/ContextPanel.jsx

import React, { useState, useEffect, useCallback } from 'react';
import { useAppContext } from '../context/AppContext';
import api from '../api/axios'; // Brauchen wir für die Drucklogik
import Chat from './Chat';

const getIdsInOrder = (nodes, idsToFind) => {
    let orderedIds = [];
    function traverse(node) {
        if (idsToFind.has(node.id)) {
            orderedIds.push(node.id);
        }
        if (node.children) {
            for (const child of node.children) {
                traverse(child);
            }
        }
    }
    for (const rootNode of nodes) {
        traverse(rootNode);
    }
    return orderedIds;
};

const ContextPanel = () => {
    const { selectedNodeIds, getContextContent, treeData, enterPrintPreview } = useAppContext(); 
  
  const [contextTitles, setContextTitles] = useState([]);
  const [isCopyingContent, setIsCopyingContent] = useState(false);
  const [copyContentSuccess, setCopyContentSuccess] = useState('');
  const [isCopyingTree, setIsCopyingTree] = useState(false);
  const [copyTreeSuccess, setCopyTreeSuccess] = useState('');
  const [isPrinting, setIsPrinting] = useState(false);

  useEffect(() => {
    const fetchTitles = async () => {
      if (selectedNodeIds.size > 0) {
        const { titles } = await getContextContent();
        setContextTitles(titles);
      } else {
        setContextTitles([]);
      }
    };
    fetchTitles();
  }, [selectedNodeIds, getContextContent]);

  const handleCopyContext = useCallback(async () => {
    setIsCopyingContent(true);
    setCopyContentSuccess('');
    const { content } = await getContextContent();
    if (content) {
      navigator.clipboard.writeText(content)
        .then(() => setCopyContentSuccess('Content Copied!'))
        .catch(err => setCopyContentSuccess('Failed.'));
    } else {
      setCopyContentSuccess('Nothing to copy.');
    }
    const timer = setTimeout(() => setCopyContentSuccess(''), 2000);
    setIsCopyingContent(false);
    return () => clearTimeout(timer);
  }, [getContextContent]);

  const handleCopyTree = useCallback(async () => {
    if (!treeData || treeData.length === 0) {
        setCopyTreeSuccess('Tree not loaded.');
        setTimeout(() => setCopyTreeSuccess(''), 2000);
        return;
    }
    setIsCopyingTree(true);
    setCopyTreeSuccess('');
    const formatNode = (node, level = 0) => {
        const indent = '  '.repeat(level);
        let output = `${indent}- ${node.title}\n`;
        if (node.children && node.children.length > 0) {
            output += node.children.map(child => formatNode(child, level + 1)).join('');
        }
        return output;
    };
    const formattedTree = treeData.map(rootNode => formatNode(rootNode, 0)).join('');
    try {
        await navigator.clipboard.writeText(formattedTree);
        setCopyTreeSuccess('Tree Copied!');
    } catch (err) {
        setCopyTreeSuccess('Failed.');
    }
    const timer = setTimeout(() => setCopyTreeSuccess(''), 2000);
    setIsCopyingTree(false);
    return () => clearTimeout(timer);
  }, [treeData]);

    const handlePrintSelection = useCallback(async () => {
    if (selectedNodeIds.size === 0) {
      alert("Please select at least one node from the tree to print.");
      return;
    }
    setIsPrinting(true);
    try {
      const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
      const nodePromises = orderedIds.map(id => api.get(`/api/nodes/${id}`));
      const nodeResponses = await Promise.all(nodePromises);
      const foundNodes = nodeResponses.map(res => res.data);
      
  
      enterPrintPreview(foundNodes);

    } catch (err) {
      console.error("Failed to fetch nodes for printing:", err);
      // Optional: Fehler im UI anzeigen
    } finally {
      setIsPrinting(false);
    }
  }, [selectedNodeIds, treeData, enterPrintPreview]);

 return (
    <div className="context-panel-container">
      
      <div className="context-selection-area">
        <h3>Context Actions</h3>
        <div className="context-selection-list">
          {contextTitles.length > 0 ? (
            <ul>
              {contextTitles.map((title, index) => <li key={index}>{title}</li>)}
            </ul>
          ) : (
            <p className="no-context-message">Select nodes to build your context.</p>
          )}
        </div>
        
        <div className="context-actions">
          <button onClick={handleCopyContext} disabled={isCopyingContent || selectedNodeIds.size === 0} className="btn btn-secondary">
            {isCopyingContent ? 'Copying...' : 'Copy Content'}
          </button>
          
          <button onClick={handleCopyTree} disabled={isCopyingTree || !treeData || treeData.length === 0} className="btn btn-secondary">
            {isCopyingTree ? 'Copying...' : 'Copy Tree'}
          </button>

          <button onClick={handlePrintSelection} disabled={isPrinting || selectedNodeIds.size === 0} className="btn btn-success">
            {isPrinting ? 'Preparing...' : `Print Selection (${selectedNodeIds.size})`}
          </button>
        </div>
        <div className="copy-success-area">
            {copyContentSuccess && <span className="copy-success">{copyContentSuccess}</span>}
            {copyTreeSuccess && <span className="copy-success">{copyTreeSuccess}</span>}
        </div>
      </div>
      
      <div className="chat-container">
        <Chat />
      </div>

    </div>
  );
};

export default ContextPanel;