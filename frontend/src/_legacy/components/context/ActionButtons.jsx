// src/components/context/ActionButtons.jsx

import React, { useState, useCallback, useMemo, lazy, Suspense, useEffect } from 'react';
import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import Dropdown from 'react-bootstrap/Dropdown';
import Form from 'react-bootstrap/Form';
import { useAppContext } from '../../context/AppContext';
import api from '../../api/axios';
import './ActionButtons.css'; 

// Service-Imports
import { copyContextContent, copyTreeStructure } from '../../../services/clipboardService';
import { exportSelectionAsEpub, exportSelectionAsMarkdown } from '../../../services/exportService';
import { getIdsInOrder, generateTocForSelectedNodes } from '../../../services/treeService';

// Import des Modals
const UpdatePreviewModal = lazy(() => import('./UpdatePreviewModal')); 

// WICHTIG: Die Komponente mit React.memo umwickeln, damit sie nur neu rendert,
// wenn sich ihre Props (wie onNodeUpdate) tatsächlich ändern.
const ActionButtons = React.memo(function ActionButtons({ onNodeUpdate }) {
  const { 
    selectedNodeIds, 
    getContextContent,
    chatSessionId,
    treeData, 
    enterPrintPreview, 
    activeVault,
    selectedModel
  } = useAppContext();
  
  // Stabile ID für Abhängigkeitsarrays verwenden
  const activeVaultId = activeVault?.id;

  const [isLoading, setIsLoading] = useState({
    copyContent: false,
    copyTree: false,
    exportEpub: false,
    exportMd: false,
    print: false,
    // Der Key für das AI-Update fehlt hier nicht, aber
    // es ist eine separate Variable `isLoadingProposal`. Das ist okay.
  });
  const [feedback, setFeedback] = useState({ message: '', type: 'success' });
  
  const [updateTargetNodeId, setUpdateTargetNodeId] = useState('');
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [updateData, setUpdateData] = useState({ original: '', proposed: '' });
  const [isLoadingProposal, setIsLoadingProposal] = useState(false);
  const [isSavingUpdate, setIsSavingUpdate] = useState(false);

  const hasSelection = selectedNodeIds.size > 0;
  const hasTree = treeData && treeData.length > 0;

  const showFeedback = useCallback((message, type = 'success') => {
    setFeedback({ message, type });
    setTimeout(() => setFeedback({ message: '', type: 'success' }), 4000);
  }, []);

  // KORREKTUR: Alle Abhängigkeiten sind jetzt stabil.
  const handleCopyContent = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, copyContent: true }));
    try {
      await copyContextContent(getContextContent);
      showFeedback('Inhalt erfolgreich kopiert!');
    } catch (error) {
      showFeedback(error.message || 'Kopieren fehlgeschlagen.', 'error'); 
    } finally {
      setTimeout(() => setIsLoading(prev => ({ ...prev, copyContent: false })), 200);
    }
  }, [getContextContent, showFeedback]);

  const handleCopyTree = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, copyTree: true }));
    try {
      await copyTreeStructure(treeData);
      showFeedback('Baumstruktur erfolgreich kopiert!');
    } catch (error) {
      showFeedback(error.message || 'Kopieren fehlgeschlagen.', 'error');
    } finally {
        setTimeout(() => setIsLoading(prev => ({ ...prev, copyTree: false })), 200);
    }
  }, [treeData, showFeedback]);
  
  const handleExportEpub = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, exportEpub: true }));
    try {
      // WICHTIG: Hier das volle `activeVault`-Objekt übergeben, wie vom Service benötigt.
      // Die Abhängigkeit ist aber die stabile ID.
      await exportSelectionAsEpub(treeData, selectedNodeIds, activeVault);
      showFeedback('EPUB-Export gestartet!');
    } catch (error) {
      showFeedback(error.message || 'EPUB-Export fehlgeschlagen.', 'error');
    } finally {
      setIsLoading(prev => ({ ...prev, exportEpub: false }));
    }
  }, [treeData, selectedNodeIds, activeVault, showFeedback]); // `activeVault` bleibt hier, da das Objekt gebraucht wird, aber die Kette ist jetzt stabil.

  const handleExportMd = useCallback(async () => {
    setIsLoading(prev => ({ ...prev, exportMd: true }));
    try {
      await exportSelectionAsMarkdown(treeData, selectedNodeIds, activeVault);
      showFeedback('Markdown-Export gestartet!');
    } catch (error) {
      showFeedback(error.message || 'Markdown-Export fehlgeschlagen.', 'error');
    } finally {
      setIsLoading(prev => ({ ...prev, exportMd: false }));
    }
  }, [treeData, selectedNodeIds, activeVault, showFeedback]);

  const handlePrint = useCallback(async () => {
    if (selectedNodeIds.size === 0) {
        showFeedback("Bitte Nodes zum Drucken auswählen.", 'error');
        return;
    }
    if (!activeVaultId) return;

      setIsLoading(prev => ({ ...prev, print: true }));
      try {
          // Eine einzige POST-Anfrage an den neuen Endpunkt
          const response = await api.post(`/api/vaults/${activeVaultId}/nodes/bulk-get`, {
              node_ids: Array.from(selectedNodeIds)
          });

          const nodesWithContent = response.data;

          // Die restliche Logik bleibt wieder gleich
          const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
          const sortedNodes = nodesWithContent.sort((a, b) => orderedIds.indexOf(a.id) - orderedIds.indexOf(b.id));
          const toc = generateTocForSelectedNodes(treeData, selectedNodeIds);

          enterPrintPreview({ nodes: sortedNodes, toc: toc });

      } catch (error) {
          console.error("Fehler beim Erstellen der Druckvorschau:", error);
          showFeedback('Druckvorschau konnte nicht erstellt werden.', 'error');
      } finally {
          setTimeout(() => setIsLoading(prev => ({ ...prev, print: false })), 200);
      }
  }, [treeData, selectedNodeIds, activeVaultId, enterPrintPreview, showFeedback]);
  
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

  // Effekt, um die Auswahl zurückzusetzen, wenn die Kontext-Nodes sich ändern
  useEffect(() => {
    if (!contextNodesForDropdown.find(n => n.id === updateTargetNodeId)) {
      setUpdateTargetNodeId('');
    }
  }, [contextNodesForDropdown, updateTargetNodeId]);

    const handleProposeUpdate = useCallback(async () => {
        // --- ANPASSUNG 1: Session-ID wird nun benötigt ---
        // Stellen Sie sicher, dass `activeSessionId` aus Ihrem State oder den Props kommt.
        if (!updateTargetNodeId || !activeVaultId || !selectedModel || !chatSessionId) {
            showFeedback("Ziel, Vault, Modell oder aktive Session nicht ausgewählt.", "error");
            return;
        }

        setIsLoadingProposal(true);
        try {
            // --- ANPASSUNG 2: Chat-Verlauf wird nicht mehr aus dem sessionStorage geladen ---
            // const savedHistory = JSON.parse(sessionStorage.getItem('chatHistory') || '[]');
            // const chatHistoryText = savedHistory.map(m => `${m.role}: ${m.content}`).join('\n\n');

            // --- ANPASSUNG 3: Der Payload wurde an die neue API angepasst ---
            // Er sendet jetzt `session_id` anstelle von `chat_history` und `vault_id`.
            const payload = {
                session_id: chatSessionId, // Neue Anforderung
                context_node_ids: Array.from(selectedNodeIds),
                model: selectedModel
            };

            // --- ANPASSUNG 4: Die API-URL wurde gemäß dem Testfall aktualisiert. ---
            // Die `vault_id` ist jetzt Teil des URL-Pfads.
            const response = await api.post(
                `/api/vaults/${activeVaultId}/nodes/${updateTargetNodeId}/propose-update`,
                payload
            );

            setUpdateData({
                original: response.data.original_content,
                proposed: response.data.proposed_content
            });
            setIsUpdateModalOpen(true);
        } catch (error) {
            // 1. Loggen Sie den gesamten Fehler in der Entwicklerkonsole.
            //    Das ist Gold wert für die Fehlersuche!
            console.error("Fehler beim Abrufen des AI-Vorschlags:", error);

            // 2. Zeigen Sie dem Benutzer eine spezifischere Nachricht, falls verfügbar.
            //    Wir versuchen, die Fehlermeldung vom Server zu extrahieren.
            const serverMessage = error.response?.data?.error; // Sicherer Zugriff mit Optional Chaining (?.)
            const feedbackMessage = serverMessage
                ? `Fehler: ${serverMessage}`
                : "Fehler beim Abrufen des AI-Vorschlags.";

            showFeedback(feedbackMessage, "error");
        } finally {
            setIsLoadingProposal(false);
        }
        // --- ANPASSUNG 5: Die `activeSessionId` zu den Abhängigkeiten hinzufügen ---
    }, [updateTargetNodeId, activeVaultId, selectedNodeIds, selectedModel, showFeedback, chatSessionId]);

  const handleAcceptUpdate = useCallback(async () => {
    if (!updateTargetNodeId) return;
    
    setIsSavingUpdate(true);
    // Die prop `onNodeUpdate` ist jetzt dank der Korrekturen in NodesView stabil.
    const success = await onNodeUpdate(updateTargetNodeId, { content: updateData.proposed });
    setIsSavingUpdate(false);
    
    if (success) {
        setIsUpdateModalOpen(false);
        showFeedback('Node erfolgreich aktualisiert!');
    } else {
        showFeedback("Speichern des Updates fehlgeschlagen.", "error");
    }
  }, [updateTargetNodeId, updateData.proposed, onNodeUpdate, showFeedback]);

  return (
    <>
      <div className="context-actions mt-3">
        <h5 className="mb-2">Kontext-Aktionen</h5>
        
        {/* Hauptaktionen */}
        <ButtonGroup className="w-100 mb-2">
          <Button 
            variant="primary" 
            size="sm" 
            onClick={handleCopyContent} 
            disabled={!hasSelection || isLoading.copyContent}
          >
            {isLoading.copyContent ? '...' : 'Inhalt kopieren'}
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

        
        {/* AI Update Sektion mit Trennlinie und Abstand */}
        <div className="ai-update-section border-top pt-2 mt-3">
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

      <Suspense fallback={null}> {}
        <UpdatePreviewModal
          show={isUpdateModalOpen}
          onHide={() => setIsUpdateModalOpen(false)}
          onAccept={handleAcceptUpdate}
          oldContent={updateData.original}
          newContent={updateData.proposed}
          isUpdating={isSavingUpdate}
        />
      </Suspense>
    </>
  );
});

export default ActionButtons;