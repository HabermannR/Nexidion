import React, { useState, useCallback, useMemo } from 'react';
import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Dropdown from 'react-bootstrap/Dropdown';
import Form from 'react-bootstrap/Form';
import { useAppContext } from '../../context/AppContext';
import api from '../../api/axios';
import './ActionButtons.css'; 
import qs from 'qs';

// Service-Imports
import { copyContextContent, copyTreeStructure } from '../../services/clipboardService';
import { exportSelectionAsEpub, exportSelectionAsMarkdown } from '../../services/exportService';
import { getIdsInOrder, generateTocForSelectedNodes } from '../../services/treeService';

// Import des Modals
import UpdatePreviewModal from './UpdatePreviewModal'; 

export default function ActionButtons({ onNodeUpdate }) {
  const { selectedNodeIds, getContextContent, treeData, enterPrintPreview, activeVault } = useAppContext();
  
  const [isLoading, setIsLoading] = useState({
    copyContent: false,
    copyTree: false,
    exportEpub: false,
    exportMd: false,
    print: false,
  });
  const [feedback, setFeedback] = useState({ message: '', type: 'success' }); // Erweitert für Fehler/Erfolg
  
  // State für den AI-Update-Prozess
  const [updateTargetNodeId, setUpdateTargetNodeId] = useState('');
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [updateData, setUpdateData] = useState({ original: '', proposed: '' });
  const [isLoadingProposal, setIsLoadingProposal] = useState(false);
  const [isSavingUpdate, setIsSavingUpdate] = useState(false);

  const hasSelection = selectedNodeIds.size > 0;
  const hasTree = treeData && treeData.length > 0;

  // Hilfsfunktion für Feedback-Nachrichten
  const showFeedback = useCallback((message, type = 'success') => {
    setFeedback({ message, type });
    setTimeout(() => setFeedback({ message: '', type: 'success' }), 4000);
  }, []);

  // KORREKTUR: Der Handler muss async sein, um await zu verwenden
  const handleCopyContent = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, copyContent: true }));
    try {
      // KORREKTUR: Wir warten auf das Ergebnis der asynchronen Funktion
      await copyContextContent(getContextContent);
      showFeedback('Inhalt erfolgreich kopiert!');
    } catch (error) {
      console.error("Fehler beim Kopieren des Inhalts:", error);
      // KORREKTUR: Wir zeigen die spezifische Fehlermeldung aus dem Service an
      showFeedback(error.message, 'error'); 
    } finally {
      // Das Timeout hier ist gut, um ein kurzes "Aufblitzen" zu verhindern
      setTimeout(() => setIsLoading(prev => ({ ...prev, copyContent: false })), 200);
    }
  }, [getContextContent, showFeedback]);

  // KORREKTUR: Auch dieser Handler muss async sein
  const handleCopyTree = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, copyTree: true }));
    try {
      // KORREKTUR: Wir warten auf das Ergebnis der asynchronen Funktion
      await copyTreeStructure(treeData);
      showFeedback('Baumstruktur erfolgreich kopiert!');
    } catch (error) {
      console.error("Fehler beim Kopieren des Baums:", error);
      // KORREKTUR: Wir zeigen die spezifische Fehlermeldung aus dem Service an
      showFeedback(error.message, 'error');
    } finally {
        setTimeout(() => setIsLoading(prev => ({ ...prev, copyTree: false })), 200);
    }
  }, [treeData, showFeedback]);
  
  // Die anderen Handler sind bereits korrekt als async deklariert.
  // Wir können aber auch hier die Fehlerbehandlung verbessern.
  const handleExportEpub = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, exportEpub: true }));
    try {
      const success = await exportSelectionAsEpub(treeData, selectedNodeIds, activeVault);
      if (success) {
        showFeedback('EPUB-Export gestartet!');
      } else if (selectedNodeIds.size > 0) {
        showFeedback('Export fehlgeschlagen oder abgebrochen.', 'error');
      }
    } catch (error) {
      console.error("Fehler beim EPUB-Export:", error);
      // KORREKTUR: Auch hier die spezifische Fehlermeldung anzeigen
      showFeedback(error.message || 'EPUB-Export ist fehlgeschlagen.', 'error');
    } finally {
      setIsLoading(prev => ({ ...prev, exportEpub: false }));
    }
  }, [treeData, selectedNodeIds, activeVault, showFeedback]);

  // KORRIGIERT: Expliziter async Handler für Markdown-Export
  const handleExportMd = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, exportMd: true }));
    try {
      // Übergebe hier das activeVault-Objekt
      const success = await exportSelectionAsMarkdown(treeData, selectedNodeIds, activeVault);
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
  }, [treeData, selectedNodeIds, activeVault, showFeedback]); // activeVault als Abhängigkeit hinzufügen

  const handlePrint = useCallback(async () => { // Die Funktion muss jetzt async sein
    if (selectedNodeIds.size === 0) {
        showFeedback("Bitte Nodes zum Drucken auswählen.");
        return;
    }

    setIsLoading(prev => ({ ...prev, print: true }));

    try {
        const nodeIds = Array.from(selectedNodeIds);

        const response = await api.get('/api/nodes/details', {
            params: {
                vault_id: activeVault.id,
                node_ids: nodeIds
            },
            // DIESE ZEILEN SIND DIE LÖSUNG:
            paramsSerializer: params => {
                return qs.stringify(params, { arrayFormat: 'repeat' });
            }
        });

        const nodesWithContent = response.data; // Das ist jetzt unser Array mit vollen Nodes

        if (!nodesWithContent || nodesWithContent.length === 0) {
            throw new Error("Could not fetch node details from server.");
        }

        // --- DATEN-NACHLADEN ENDE ---

        // 2. Sortiere die Nodes in der visuellen Reihenfolge des Baumes.
        const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
        const sortedNodes = nodesWithContent.sort((a, b) => {
            return orderedIds.indexOf(a.id) - orderedIds.indexOf(b.id);
        });

        // 3. Generiere das Inhaltsverzeichnis (Table of Contents).
        const toc = generateTocForSelectedNodes(treeData, selectedNodeIds);

        // 4. Rufe enterPrintPreview mit den vollständigen Daten auf.
        enterPrintPreview({
            nodes: sortedNodes,
            toc: toc
        });
        
    } catch (error) {
        console.error("Fehler bei der Druckvorbereitung:", error);
        showFeedback('Druckvorschau konnte nicht erstellt werden.');
    } finally {
        setTimeout(() => setIsLoading(prev => ({ ...prev, print: false })), 200);
    }
}, [treeData, selectedNodeIds, activeVault, enterPrintPreview, showFeedback]); // activeVault als Abhängigkeit hinzufügen
  
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
    // VAULT-FIX: Guard Clause, um sicherzustellen, dass ein Vault aktiv ist.
    if (!updateTargetNodeId || !activeVault) return;
    
    setIsLoadingProposal(true);
    try {
      const savedHistory = JSON.parse(sessionStorage.getItem('chatHistory') || '[]');
      const chatHistoryText = savedHistory.map(m => `${m.role}: ${m.content}`).join('\n\n');
      
      const selectedModel = localStorage.getItem('selectedModel') || 'gemini-2.5-pro'; // Sinnvoller Fallback

      const payload = {
        chat_history: chatHistoryText,
        context_node_ids: Array.from(selectedNodeIds),
        vault_id: activeVault.id,
        model: selectedModel // Das Modell wird jetzt mitgesendet!
      };

      const response = await api.post(`/api/nodes/${updateTargetNodeId}/propose-update`, payload);
      
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
    if (!updateTargetNodeId || !activeVault?.id) return; // Sicherer Check
    
    setIsSavingUpdate(true);
    
    // KORREKTUR: Die vault_id mit übergeben
    const success = await onNodeUpdate(updateTargetNodeId, { content: updateData.proposed }, activeVault.id);
    
    setIsSavingUpdate(false);
    
    if (success) {
        setIsUpdateModalOpen(false);
        showFeedback('Node erfolgreich aktualisiert!');
    } else {
        // Optional: Feedback geben, falls das Update im Parent fehlschlägt
        alert("Failed to save the update. Please check the console.");
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

      {feedback.message && (
        <div className={`small mt-2 text-center ${feedback.type === 'error' ? 'text-danger' : 'text-success'}`}>
          {feedback.message}
        </div>
      )}

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