// src/features/workspace/right-panel/ToolsTab.jsx

import React, {useState, useEffect, useMemo, useCallback} from 'react';
import { Button, Alert, Form } from 'react-bootstrap';
import { useMutation } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import apiClient from '../../../api/apiClient';
import { useWorkspaceStore } from '../workspaceStore';
import UpdatePreviewModal from './UpdatePreviewModal';
import { useSaveNodeContent } from '../../../services/useSaveNodeContent';

/**
 * Custom Hook für den API-Aufruf, um einen Update-Vorschlag zu erhalten.
 * Angepasst an den neuen Endpunkt: .../tools/{node_id}/propose-update
 *
 * @param {string} targetNodeId - Die ID des Ziel-Nodes, die in die URL eingefügt wird.
 * @param {object} options - Standard-Optionen für useMutation (onSuccess, onError, etc.).
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
    const [targetNodeId, setTargetNodeId] = useState('');
    const [isModalOpen, setIsModalOpen] = useState(false);

    const activeChatSessionId = useWorkspaceStore(state => state.activeChatSessionId);
    const chatModel = useWorkspaceStore(state => state.chatModel);

    // This efficiently finds the title of the currently selected target node.
    const targetNodeTitle = useMemo(() => {
        if (!targetNodeId) return '';
        const target = selectedNodes.find(node => node.id === targetNodeId);
        return target ? target.title : '';
    }, [targetNodeId, selectedNodes]);


    const selectedIdsKey = useMemo(() => selectedNodes.map(n => n.id).sort().join(','), [selectedNodes]);
    useEffect(() => {
        const isTargetStillSelected = selectedNodes.some(node => node.id === targetNodeId);
        if (!isTargetStillSelected && targetNodeId !== '') setTargetNodeId('');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedIdsKey, targetNodeId]);

    const proposeUpdateMutation = useProposeNodeUpdate(targetNodeId, { onSuccess: () => setIsModalOpen(true) });
    const acceptUpdateMutation = useSaveNodeContent({
        onSuccess: () => {
            setIsModalOpen(false);
            setTargetNodeId('');
        },
    });

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


    if (selectedNodes.length === 0) {
        return <div className="small text-muted">Select one or more nodes in the tree to see available tools.</div>;
    }

    const canPropose = targetNodeId && chatModel;

    return (
        <div>
            <h6 className="text-muted">Tools for Selected Nodes ({selectedNodes.length})</h6>

            <div className="border-top pt-3 mt-3">
                <label htmlFor="ai-target-node" className="form-label small fw-bold">Update Node with AI</label>
                <div className="d-flex gap-2">
                    <Form.Select
                        id="ai-target-node"
                        size="sm"
                        value={targetNodeId}
                        onChange={(e) => setTargetNodeId(e.target.value)}
                        disabled={proposeUpdateMutation.isPending}
                    >
                        <option value="">Choose target...</option>
                        {selectedNodes.map(node => <option key={node.id} value={node.id}>{node.title}</option>)}
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