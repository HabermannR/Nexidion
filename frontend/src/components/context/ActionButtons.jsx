import React, { useState, useCallback, useMemo } from 'react';
import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Dropdown from 'react-bootstrap/Dropdown';
import Form from 'react-bootstrap/Form';
import { useAppContext } from '../../context/AppContext';
import api from '../../api/axios';
import './ActionButtons.css'; 

// Service-Imports
import { copyContextContent, copyTreeStructure } from '../../services/clipboardService';
import { exportSelectionAsEpub, exportSelectionAsMarkdown } from '../../services/exportService';
// Diese Services werden hier nicht direkt genutzt, aber ich lasse sie drin, falls sie an anderer Stelle relevant sind.
// import { getIdsInOrder, generateTocForSelectedNodes } from '../../services/treeService';

// Import des Modals
import UpdatePreviewModal from './UpdatePreviewModal'; 

export default function ActionButtons({ onNodeUpdate }) {
  const { selectedNodeIds, getContextContent, treeData, enterPrintPreview } = useAppContext();
  
  // State für Ladezustände und Feedback
  const [isLoading, setIsLoading] = useState({
    copyContent: false,
    copyTree: false,
    exportEpub: false,
    exportMd: false,
    print: false,
  });
  const [feedback, setFeedback] = useState('');
  
  // State für den AI-Update-Prozess
  const [updateTargetNodeId, setUpdateTargetNodeId] = useState('');
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [updateData, setUpdateData] = useState({ original: '', proposed: '' });
  const [isLoadingProposal, setIsLoadingProposal] = useState(false);
  const [isSavingUpdate, setIsSavingUpdate] = useState(false);

  const hasSelection = selectedNodeIds.size > 0;
  const hasTree = treeData && treeData.length > 0;

  // Hilfsfunktion für Feedback-Nachrichten
  const showFeedback = useCallback((message) => {
    setFeedback(message);
    setTimeout(() => setFeedback(''), 3000);
  }, []);

  // ===================================================================
  // KORRIGIERTE ACTION HANDLER
  // Wir definieren jeden Handler explizit, um async/await korrekt zu steuern.
  // ===================================================================

  const handleCopyContent = useCallback(() => {
    setIsLoading(prev => ({ ...prev, copyContent: true }));
    try {
      copyContextContent(getContextContent);
      showFeedback('Inhalt in die Zwischenablage kopiert!');
    } catch (error) {
      console.error("Fehler beim Kopieren des Inhalts:", error);
      showFeedback('Kopieren fehlgeschlagen.');
    } finally {
      setTimeout(() => setIsLoading(prev => ({ ...prev, copyContent: false })), 200);
    }
  }, [getContextContent, showFeedback]);

  const handleCopyTree = useCallback(() => {
    setIsLoading(prev => ({ ...prev, copyTree: true }));
    try {
      copyTreeStructure(treeData);
      showFeedback('Baumstruktur in die Zwischenablage kopiert!');
    } catch (error) {
      console.error("Fehler beim Kopieren des Baums:", error);
      showFeedback('Kopieren fehlgeschlagen.');
    } finally {
        setTimeout(() => setIsLoading(prev => ({ ...prev, copyTree: false })), 200);
    }
  }, [treeData, showFeedback]);
  
  // KORRIGIERT: Expliziter async Handler für EPUB-Export
  const handleExportEpub = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, exportEpub: true }));
    try {
      const success = await exportSelectionAsEpub(treeData, selectedNodeIds);
      if (success) {
        showFeedback('EPUB-Export gestartet!');
      } else if (selectedNodeIds.size > 0) {
        showFeedback('Export fehlgeschlagen oder abgebrochen.');
      }
    } catch (error) {
      console.error("Fehler beim EPUB-Export:", error);
      showFeedback('EPUB-Export ist fehlgeschlagen.');
    } finally {
      setIsLoading(prev => ({ ...prev, exportEpub: false }));
    }
  }, [treeData, selectedNodeIds, showFeedback]);

  // KORRIGIERT: Expliziter async Handler für Markdown-Export
  const handleExportMd = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, exportMd: true }));
    try {
      const success = await exportSelectionAsMarkdown(treeData, selectedNodeIds);
      if (success) {
        showFeedback('Markdown-Export gestartet!');
      } else if (selectedNodeIds.size > 0) {
        showFeedback('Export fehlgeschlagen oder abgebrochen.');
      }
    } catch (error) {
      console.error("Fehler beim Markdown-Export:", error);
      showFeedback('Markdown-Export ist fehlgeschlagen.');
    } finally {
      setIsLoading(prev => ({ ...prev, exportMd: false }));
    }
  }, [treeData, selectedNodeIds, showFeedback]);

  const handlePrint = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, print: true }));
    try {
        await enterPrintPreview();
        // Feedback wird durch den Kontext gehandhabt oder ist nicht nötig
    } catch(error) {
        console.error("Fehler bei der Druckvorbereitung:", error);
        showFeedback('Druckvorschau konnte nicht erstellt werden.');
    } finally {
        setIsLoading(prev => ({ ...prev, print: false }));
    }
  }, [enterPrintPreview, showFeedback]);
  
  // ===================================================================
  // Logik für AI-Update (unverändert)
  // ===================================================================
  const flattenedNodes = useMemo(() => {
      const allNodes = [];
      const flatten = (nodes) => {
          for (const node of nodes) {
              allNodes.push({ id: node.id, title: node.title });
              if (node.children) flatten(node.children);
          }
      };
      if (treeData) flatten(treeData);
      return allNodes;
  }, [treeData]);

  const contextNodesForDropdown = useMemo(() => {
      return flattenedNodes.filter(node => selectedNodeIds.has(node.id));
  }, [selectedNodeIds, flattenedNodes]);

  const handleProposeUpdate = async () => {
    if (!updateTargetNodeId) return;
    setIsLoadingProposal(true);
    try {
      const savedHistory = JSON.parse(sessionStorage.getItem('chatHistory') || '[]');
      const chatHistoryText = savedHistory.map(m => `${m.role}: ${m.content}`).join('\n\n');
      
      const response = await api.post(`/api/nodes/${updateTargetNodeId}/propose-update`, {
        chat_history: chatHistoryText,
        context_node_ids: Array.from(selectedNodeIds)
      });
      
      setUpdateData({
        original: response.data.original_content,
        proposed: response.data.proposed_content
      });
      setIsUpdateModalOpen(true);
    } catch (error) {
      console.error("Failed to propose update:", error);
      alert("Error getting update proposal from AI.");
    } finally {
      setIsLoadingProposal(false);
    }
  };

  const handleAcceptUpdate = async () => {
    if (!updateTargetNodeId) return;
    
    setIsSavingUpdate(true);
    const success = await onNodeUpdate(updateTargetNodeId, updateData.proposed);
    setIsSavingUpdate(false);
    
    if (success) {
        setIsUpdateModalOpen(false);
        showFeedback('Node erfolgreich aktualisiert!');
    }
  };

  return (
    <>
      <div className="context-actions mt-3">
        <h5 className="mb-2">Aktionen</h5>
        
        {/* REIHE 1: Hauptaktionen */}
        <ButtonGroup className="w-100 mb-2">
          <Button 
            variant="primary" 
            size="sm" 
            onClick={handleCopyContent} 
            disabled={!hasSelection || isLoading.copyContent}
          >
            {isLoading.copyContent ? 'Kopiere...' : 'Inhalt kopieren'}
          </Button>

          <Button 
            variant="outline-secondary" 
            size="sm" 
            onClick={handleCopyTree} 
            disabled={!hasTree || isLoading.copyTree}
          >
            {isLoading.copyTree ? '...' : 'Baum kopieren'}
          </Button>

          <Dropdown as={ButtonGroup}>
            <Dropdown.Toggle split variant="outline-secondary" size="sm" disabled={!hasSelection} />
            <Dropdown.Menu>
              <Dropdown.Item onClick={handlePrint} disabled={isLoading.print}>
                {isLoading.print ? 'Bereite vor...' : `Drucken (${selectedNodeIds.size})`}
              </Dropdown.Item>
              <Dropdown.Divider />
              <Dropdown.Header>Exportieren</Dropdown.Header>
              <Dropdown.Item onClick={handleExportMd} disabled={isLoading.exportMd}>
                {isLoading.exportMd ? 'Exportiere...' : 'Als Markdown'}
              </Dropdown.Item>
              <Dropdown.Item onClick={handleExportEpub} disabled={isLoading.exportEpub}>
                {isLoading.exportEpub ? 'Exportiere...' : 'Als EPUB'}
              </Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
        </ButtonGroup>
        
        {/* REIHE 2: AI Update Sektion */}
        <div className="ai-update-section border-top pt-2">
            <label htmlFor="ai-target-node" className="form-label small fw-bold">Update mit AI</label>
            <div className="d-flex gap-2">
                <Form.Select 
                    id="ai-target-node"
                    size="sm"
                    value={updateTargetNodeId}
                    onChange={(e) => setUpdateTargetNodeId(e.target.value)}
                    disabled={contextNodesForDropdown.length === 0 || isLoadingProposal}
                >
                    <option value="">Ziel auswählen...</option>
                    {contextNodesForDropdown.map(node => (
                        <option key={node.id} value={node.id}>{node.title}</option>
                    ))}
                </Form.Select>
                
                <Button 
                    variant="info"
                    size="sm"
                    onClick={handleProposeUpdate}
                    disabled={!updateTargetNodeId || isLoadingProposal}
                    className="flex-shrink-0"
                >
                    {isLoadingProposal ? 'Analysiere...' : 'Vorschlag'}
                </Button>
            </div>
        </div>

      </div>

      {feedback && <div className="text-success small mt-2 text-center">{feedback}</div>}

      <UpdatePreviewModal
        show={isUpdateModalOpen}
        onHide={() => setIsUpdateModalOpen(false)}
        onAccept={handleAcceptUpdate}
        oldContent={updateData.original}
        newContent={updateData.proposed}
        isUpdating={isSavingUpdate}
      />
    </>
  );
}