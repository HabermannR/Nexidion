import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Button, Alert, Form } from 'react-bootstrap';
import { useMutation } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useSaveNodeContent } from '../nodes/hooks/useSaveNodeContent.js';
import { copyContextContent, copyTreeStructure } from '../../lib/clipboardService.js';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery'
import UpdatePreviewModal from '../../components/UpdatePreviewModal.jsx';

/**
 * Custom Hook für den API-Aufruf, um einen Update-Vorschlag zu erhalten.
 */
const useProposeNodeUpdate = (targetNodeId, options) => {
    const { vaultId } = useParams();
    return useMutation({
        mutationFn: ({ contextNodeIds, chatSessionId, model }) => {
            if (!targetNodeId) {
                return Promise.reject(new Error("No target node selected."));
            }
            const payload = { context_node_ids: contextNodeIds, model: model };
            if (chatSessionId) payload.session_id = chatSessionId;
            return apiClient.post(`/api/vaults/${vaultId}/tools/${targetNodeId}/propose-update`, payload).then(res => res.data);
        },
        ...options,
    });
};

export default function ToolsTab() {
    // --- LOKALER UI-ZUSTAND ---
    const [targetNodeId, setTargetNodeId] = useState('');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [copyContentStatus, setCopyContentStatus] = useState('idle'); // idle, copying, success, error
    const [copyContentError, setCopyContentError] = useState(null);
    const [copyTreeStatus, setCopyTreeStatus] = useState('idle');     // idle, copying, success, error
    const [copyTreeError, setCopyTreeError] = useState(null);

    // --- DATEN AUS GLOBALEN STORES & CONTEXT ---
    const { vaultId } = useParams();
    const {
        data,
        isLoading: isTreeLoading,
        isSuccess: isTreeReady,
    } = useVaultTreeQuery(vaultId);

    const treeData = data?.tree || [];
    const allNodesFlat = data?.allNodesFlat || [];

    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const activeChatSessionId = useWorkspaceStore(state => state.activeChatSessionId);
    const chatModel = useWorkspaceStore(state => state.chatModel);

    // KORREKTUR 1: Die "Auswahl" basiert direkt auf dem Store, nicht auf den geladenen Baumdaten.
    // Dies ist die primäre Quelle der Wahrheit für die Aktivierung der UI-Elemente.
    const hasSelection = selectedNodeIds.size > 0;

        const selectedNodes = useMemo(() => {
        // Dieser Hook berechnet jetzt nur noch die _Details_ der Auswahl (z.B. für die Dropdown-Liste).
        // Er ist nicht mehr für die Logik zum Deaktivieren der Buttons verantwortlich.
        if (!isTreeReady || !allNodesFlat || selectedNodeIds.size === 0) {
            return [];
        }

        const nodeMap = new Map(allNodesFlat.map(node => [node.id, node]));
        return Array.from(selectedNodeIds)
            .map(id => {
                const node = nodeMap.get(id);
                return { id, title: node?.title || 'Loading...' }; // Zeige "Loading..." an, falls Node noch nicht im Map ist
            })
            .sort((a, b) => a.title.localeCompare(b.title));
    }, [selectedNodeIds, allNodesFlat, isTreeReady]);

    // --- MEMOIZED VALUES & EFFECTS ---
    const targetNodeTitle = useMemo(() => {
        if (!targetNodeId) return '';
        const target = selectedNodes.find(node => node.id === targetNodeId);
        return target ? target.title : '';
    }, [targetNodeId, selectedNodes]);

    const selectedIdsKey = useMemo(() => Array.from(selectedNodeIds).sort().join(','), [selectedNodeIds]);
    useEffect(() => {
        // Stellt sicher, dass der Target-Node zurückgesetzt wird, wenn er aus der Auswahl entfernt wird
        const isTargetStillSelected = selectedNodeIds.has(targetNodeId);
        if (!isTargetStillSelected && targetNodeId !== '') setTargetNodeId('');
    }, [selectedIdsKey, targetNodeId]); // Abhängigkeit auf selectedNodeIds Key und nicht auf selectedNodes Objekt geändert

    // --- MUTATIONS (SCHREIBENDE OPERATIONEN) ---
    const proposeUpdateMutation = useProposeNodeUpdate(targetNodeId, {
        onSuccess: () => setIsModalOpen(true)
    });

    const acceptUpdateMutation = useSaveNodeContent({
        onSuccess: () => {
            setIsModalOpen(false);
            setTargetNodeId('');
        },
    });

    // --- HANDLER FÜR UI-AKTIONEN ---
    const handleProposeUpdate = useCallback(() => {
        if (!targetNodeId || !chatModel) return;
        proposeUpdateMutation.mutate({
            contextNodeIds: Array.from(selectedNodeIds), // Direkt aus dem Store nehmen
            chatSessionId: activeChatSessionId,
            model: chatModel.id
        });
    }, [targetNodeId, chatModel, selectedNodeIds, activeChatSessionId, proposeUpdateMutation]);

    const proposedContentForUpdate = proposeUpdateMutation.data?.proposed_content;

    const handleAcceptUpdate = useCallback(() => {
        if (proposedContentForUpdate && acceptUpdateMutation.mutate) {
            acceptUpdateMutation.mutate({
                nodeId: targetNodeId,
                title: targetNodeTitle,
                content: proposedContentForUpdate,
            });
        }
    }, [acceptUpdateMutation, proposedContentForUpdate, targetNodeId, targetNodeTitle]);

    const handleCopyContent = useCallback(async () => {
        setCopyContentStatus('copying');
        setCopyContentError(null);

        const getContextContentForApi = async () => {
            const ids = Array.from(selectedNodeIds); // Direkt aus dem Store nehmen
            if (ids.length === 0) return { content: '' };
            try {
                const res = await apiClient.post(`/api/vaults/${vaultId}/nodes/content`, { node_ids: ids });
                return res.data;
            } catch (apiError) {
                throw new Error(apiError.response?.data?.error || 'Node-Inhalt konnte nicht vom Server geladen werden.');
            }
        };

        try {
            await copyContextContent(getContextContentForApi);
            setCopyContentStatus('success');
            setTimeout(() => setCopyContentStatus('idle'), 2000);
        } catch (error) {
            setCopyContentError(error.message);
            setCopyContentStatus('error');
        }
    }, [selectedNodeIds, vaultId]);

    const handleCopyTree = useCallback(async () => {
        setCopyTreeStatus('copying');
        setCopyTreeError(null);

        try {
            await copyTreeStructure(treeData);
            setCopyTreeStatus('success');
            setTimeout(() => setCopyTreeStatus('idle'), 2000);
        } catch (error) {
            setCopyTreeError(error.message);
            setCopyTreeStatus('error');
        }
    }, [treeData]);

    // KORREKTUR 2: `canPropose` nutzt jetzt direkt die neue, zuverlässige `hasSelection`-Variable.
    const canPropose = targetNodeId && chatModel && hasSelection;

    return (
        <div className="p-3">
            <h6 className="text-muted">Tools</h6>

            {/* Sektion: Node mit AI aktualisieren */}
            <div className="border-top pt-3 mt-3">
                <label htmlFor="ai-target-node" className="form-label small fw-bold">Update Node with AI</label>
                <div className="d-flex gap-2">
                    <Form.Select
                        id="ai-target-node"
                        size="sm"
                        value={targetNodeId}
                        onChange={(e) => setTargetNodeId(e.target.value)}
                        // Die Logik hier war schon korrekt, profitiert aber von der Klarheit der neuen `hasSelection`.
                        disabled={proposeUpdateMutation.isPending || isTreeLoading || !hasSelection}
                    >
                        <option value="">Choose target...</option>
                        {/* Optionen nur rendern, wenn Baumdaten bereit sind, um "Loading..." zu vermeiden */}
                        {isTreeReady && selectedNodes.map(node => <option key={node.id} value={node.id}>{node.title}</option>)}
                    </Form.Select>
                    <Button
                        variant="info"
                        size="sm"
                        onClick={handleProposeUpdate}
                        disabled={!canPropose || proposeUpdateMutation.isPending}
                        className="flex-shrink-0"
                    >
                        {proposeUpdateMutation.isPending ? 'Analyzing...' : 'Propose'}
                    </Button>
                </div>
                {proposeUpdateMutation.isError && <Alert variant="danger" className="mt-2 small p-2"><strong>Error:</strong> {proposeUpdateMutation.error.response?.data?.error || proposeUpdateMutation.error.message}</Alert>}
            </div>

            {/* Sektion: In die Zwischenablage kopieren */}
            <div className="border-top pt-3 mt-3">
                <label className="form-label small fw-bold">Copy to Clipboard</label>
                <div className="d-grid gap-2">
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={handleCopyContent}
                        // Die Logik hier profitiert direkt von der neuen `hasSelection`.
                        disabled={!hasSelection || copyContentStatus === 'copying'}
                    >
                        {copyContentStatus === 'copying' && 'Copying...'}
                        {copyContentStatus === 'success' && 'Copied!'}
                        {(copyContentStatus === 'idle' || copyContentStatus === 'error') &&
                            // KORREKTUR 3: Verwende `selectedNodeIds.size` für den Text, um zu vermeiden, dass "0" angezeigt wird, während die Details laden.
                            (hasSelection ? `Copy Content of ${selectedNodeIds.size} Node(s)` : 'Copy Content (select nodes)')
                        }
                    </Button>
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={handleCopyTree}
                        disabled={isTreeLoading || copyTreeStatus === 'copying'}
                    >
                        {copyTreeStatus === 'copying' && 'Copying...'}
                        {copyTreeStatus === 'success' && 'Copied!'}
                        {(copyTreeStatus === 'idle' || copyTreeStatus === 'error') && 'Copy Full Tree Structure'}
                    </Button>
                </div>
                {copyContentError && <Alert variant="danger" className="mt-2 small p-2"><strong>Error:</strong> {copyContentError}</Alert>}
                {copyTreeError && <Alert variant="danger" className="mt-2 small p-2"><strong>Error:</strong> {copyTreeError}</Alert>}
            </div>

            {/* Modal für die Vorschau der Änderungen */}
            {isModalOpen && proposeUpdateMutation.data && (
                <React.Suspense fallback={null}>
                    <UpdatePreviewModal
                        show={isModalOpen}
                        onHide={() => setIsModalOpen(false)}
                        onAccept={handleAcceptUpdate}
                        oldContent={proposeUpdateMutation.data.original_content}
                        newContent={proposeUpdateMutation.data.proposed_content}
                        isUpdating={acceptUpdateMutation.isPending}
                    />
                </React.Suspense>
            )}
        </div>
    );
}