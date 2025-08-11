import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Button, Alert, Form } from 'react-bootstrap';
import { useMutation } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import apiClient from '../../../api/apiClient';
import { useWorkspaceStore } from '../workspaceStore';
import { useSaveNodeContent } from '../../../services/useSaveNodeContent';
import { copyContextContent, copyTreeStructure } from '../../../services/clipboardService.js';
import { useWorkspaceData } from '../WorkspaceDataContext.js';
import UpdatePreviewModal from './UpdatePreviewModal';

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

export default function ToolsTab({ selectedNodes = [] }) {
    // --- LOKALER UI-ZUSTAND ---
    const [targetNodeId, setTargetNodeId] = useState('');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [copyContentStatus, setCopyContentStatus] = useState('idle'); // idle, copying, success, error
    const [copyContentError, setCopyContentError] = useState(null);
    const [copyTreeStatus, setCopyTreeStatus] = useState('idle');     // idle, copying, success, error
    const [copyTreeError, setCopyTreeError] = useState(null);

    // --- DATEN AUS GLOBALEN STORES & CONTEXT ---
    const { vaultId } = useParams();
    const { treeData, isTreeLoading } = useWorkspaceData(); // Holt Baumdaten via Context
    const activeChatSessionId = useWorkspaceStore(state => state.activeChatSessionId);
    const chatModel = useWorkspaceStore(state => state.chatModel);

    // --- MEMOIZED VALUES & EFFECTS ---
    const targetNodeTitle = useMemo(() => {
        if (!targetNodeId) return '';
        const target = selectedNodes.find(node => node.id === targetNodeId);
        return target ? target.title : '';
    }, [targetNodeId, selectedNodes]);

    const selectedIdsKey = useMemo(() => selectedNodes.map(n => n.id).sort().join(','), [selectedNodes]);
    useEffect(() => {
        // Stellt sicher, dass der Target-Node zurückgesetzt wird, wenn er aus der Auswahl entfernt wird
        const isTargetStillSelected = selectedNodes.some(node => node.id === targetNodeId);
        if (!isTargetStillSelected && targetNodeId !== '') setTargetNodeId('');
    }, [selectedIdsKey, targetNodeId]);

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
            contextNodeIds: selectedNodes.map(n => n.id),
            chatSessionId: activeChatSessionId,
            model: chatModel.id
        });
    }, [targetNodeId, chatModel, selectedNodes, activeChatSessionId, proposeUpdateMutation]);

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
            const ids = selectedNodes.map(n => n.id);
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
    }, [selectedNodes, vaultId]);

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

    // --- RENDER LOGIK ---
    if (selectedNodes.length === 0) {
        return <div className="small text-muted p-3">Select one or more nodes in the tree to see available tools.</div>;
    }

    const canPropose = targetNodeId && chatModel;

    return (
        <div>
            <h6 className="text-muted">Tools for Selected Nodes ({selectedNodes.length})</h6>

            {/* Sektion: Node mit AI aktualisieren */}
            <div className="border-top pt-3 mt-3">
                <label htmlFor="ai-target-node" className="form-label small fw-bold">Update Node with AI</label>
                <div className="d-flex gap-2">
                    <Form.Select id="ai-target-node" size="sm" value={targetNodeId} onChange={(e) => setTargetNodeId(e.target.value)} disabled={proposeUpdateMutation.isPending}>
                        <option value="">Choose target...</option>
                        {selectedNodes.map(node => <option key={node.id} value={node.id}>{node.title}</option>)}
                    </Form.Select>
                    <Button variant="info" size="sm" onClick={handleProposeUpdate} disabled={!canPropose || proposeUpdateMutation.isPending} className="flex-shrink-0">
                        {proposeUpdateMutation.isPending ? 'Analyzing...' : 'Propose'}
                    </Button>
                </div>
                {proposeUpdateMutation.isError && <Alert variant="danger" className="mt-2 small p-2"><strong>Error:</strong> {proposeUpdateMutation.error.response?.data?.error || proposeUpdateMutation.error.message}</Alert>}
            </div>

            {/* Sektion: In die Zwischenablage kopieren */}
            <div className="border-top pt-3 mt-3">
                <label className="form-label small fw-bold">Copy to Clipboard</label>
                <div className="d-grid gap-2">
                    <Button variant="outline-secondary" size="sm" onClick={handleCopyContent} disabled={selectedNodes.length === 0 || copyContentStatus === 'copying'}>
                        {copyContentStatus === 'copying' && 'Copying...'}
                        {copyContentStatus === 'success' && 'Copied!'}
                        {(copyContentStatus === 'idle' || copyContentStatus === 'error') && `Copy Content of ${selectedNodes.length} Node(s)`}
                    </Button>
                    <Button variant="outline-secondary" size="sm" onClick={handleCopyTree} disabled={isTreeLoading || !treeData || treeData.length === 0 || copyTreeStatus === 'copying'}>
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