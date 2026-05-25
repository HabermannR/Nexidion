// src/features/nodes/NodeContent.jsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Alert, Collapse, Form } from 'react-bootstrap';

import apiClient from '../../api/apiClient.js';
import DiffViewer from '../../components/DiffViewer.jsx';

import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useVaultTreeQuery } from './hooks/useVaultTreeQuery.js';
import { useSaveNodeContent } from './hooks/useSaveNodeContent.js';
import { useToast } from '../../components/ToastProvider.jsx';

import ContentHeader from './ContentHeader.jsx';
import NodeEditor from './NodeEditor.jsx';
import MarkdownRenderer from './MarkdownRenderer.jsx';
import AppLoading from '../../components/AppLoading.jsx';

const findPathInTree = (nodes, nodeId, currentPath =[]) => {
    for (const node of nodes) {
        const newPath = [...currentPath, {id: node.id, title: node.title, to: `/vaults/${node.vault_id}/nodes/${node.id}`}];
        if (node.id === nodeId) return newPath;
        if (node.children && node.children.length > 0) {
            const foundPath = findPathInTree(node.children, nodeId, newPath);
            if (foundPath) return foundPath;
        }
    }
    return null;
};

export default function NodeContent() {
    const { vaultId, nodeId } = useParams();
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    const [searchParams] = useSearchParams();
    const versionParam = searchParams.get('version');
    const compareParam = searchParams.get('compare');

    const { data: vaultTreeData, isLoading: isTreeLoading, isError: isTreeError } = useVaultTreeQuery(vaultId);

    const { data: versions, isLoading: isLoadingVersions, isError: isVersionsError } = useQuery({
        queryKey: ['versions', vaultId, nodeId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`).then(res => res.data),
        enabled: !!nodeId,
    });

    const { data: activeNodeData, isLoading: isLoadingNode, isError: isNodeError } = useQuery({
        queryKey: ['nodeContent', vaultId, nodeId, versionParam],
        queryFn: () => {
            const params = versionParam ? { version: versionParam } : {};
            return apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}`, { params }).then(res => res.data);
        },
        enabled: !!nodeId,
    });

    const { data: compareNodeData } = useQuery({
        queryKey: ['nodeContent', vaultId, nodeId, compareParam],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}`, { params: { version: compareParam } }).then(res => res.data),
        enabled: !!compareParam,
    });

    const setBreadcrumbPath = useWorkspaceStore((state) => state.setBreadcrumbPath);
    const setIsEditingNode = useWorkspaceStore((state) => state.setIsEditingNode);
    const toast = useToast();

    const [isEditing, setIsEditing] = useState(false);
    const [localContent, setLocalContent] = useState('');
    const [showDeleteModal, setShowDeleteModal] = useState(false);

    // AI Summary states
    const [showSummary, setShowSummary] = useState(false);
    const [isEditingSummary, setIsEditingSummary] = useState(false);
    const [editSummaryContent, setEditSummaryContent] = useState('');

    const saveContentMutation = useSaveNodeContent({
        onSuccess: () => {
            setIsEditing(false);
            queryClient.invalidateQueries({ queryKey: ['nodeContent', vaultId, nodeId] });
            queryClient.invalidateQueries({ queryKey: ['versions', vaultId, nodeId] });

            if (versionParam || compareParam) {
                const params = new URLSearchParams(searchParams);
                params.delete('version');
                params.delete('compare');
                navigate({ search: params.toString() }, { replace: true });
            }
        }
    });

    const deleteNodeMutation = useMutation({
        mutationFn: (payload) => apiClient.delete(`/api/vaults/${payload.vaultId}/nodes/${payload.nodeId}`),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ['vaultTree', variables.vaultId] });
            navigate(variables.parentId ? `/vaults/${variables.vaultId}/nodes/${variables.parentId}` : `/vaults/${variables.vaultId}`);
        },
        onError: (err) => {
            toast.error(`Could not delete node: ${err.response?.data?.error || err.message}`);
            setShowDeleteModal(false);
        },
    });

    const updateSummaryMutation = useMutation({
        mutationFn: (newSummary) => apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeId}/summary`, { ai_summary: newSummary }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nodeContent', vaultId, nodeId] });
            setIsEditingSummary(false);
        },
        onError: (err) => {
            toast.error(`Could not save summary: ${err.response?.data?.error || err.message}`);
        }
    });

    useEffect(() => {
        setIsEditing(false);
        setLocalContent('');
        setIsEditingSummary(false); // Reset summary edit mode on navigation
    }, [nodeId, versionParam]);

    // Keep the global store in sync so AgentTab knows not to clobber an
    // in-progress edit when it invalidates nodeContent on task completion.
    useEffect(() => {
        setIsEditingNode(isEditing);
        return () => setIsEditingNode(false); // clear on unmount
    }, [isEditing, setIsEditingNode]);

    useEffect(() => {
        if (vaultTreeData?.tree && nodeId) {
            const path = findPathInTree(vaultTreeData.tree, nodeId);
            setBreadcrumbPath(path ||[]);
        } else {
            setBreadcrumbPath([]);
        }
    }, [vaultTreeData, nodeId, setBreadcrumbPath]);

    useEffect(() => {
        if (activeNodeData) {
            setLocalContent(activeNodeData.content || '');
        }
    }, [activeNodeData]);

    if (!nodeId) {
        return <div className="p-4 text-center text-muted"><h4>Select a Document</h4><p>Select a document from the navigation to view it here.</p></div>;
    }

    if (isTreeLoading || isLoadingVersions || isLoadingNode) {
        return <AppLoading message="Loading document..." />;
    }

    if (isTreeError || isVersionsError || isNodeError) {
        return <Alert variant="danger" className="m-4"><h4>Error</h4><p>The document could not be loaded.</p></Alert>;
    }

    const currentBaseVersion = activeNodeData;

    if (!currentBaseVersion) {
        return (
            <div className="p-4">
                <Alert variant="info">
                    <h4>No Content</h4>
                    <p>No content found for this document yet. Start editing to create the first version.</p>
                    <Button variant="primary" onClick={() => setIsEditing(true)}>Edit</Button>
                </Alert>
            </div>
        );
    }

    const handleEditClick = () => {
        setLocalContent(currentBaseVersion.content || '');
        setIsEditing(true);
    };

    const isSaving = saveContentMutation.isPending;
    const isViewingOldVersion = currentBaseVersion.version !== currentBaseVersion.current_version;

    let sortedOldVersion = currentBaseVersion;
    let sortedNewVersion = compareParam ? compareNodeData : null;

    if (sortedNewVersion && currentBaseVersion) {
        if ((currentBaseVersion.version || 0) > (sortedNewVersion.version || 0)) {
            sortedOldVersion = sortedNewVersion;
            sortedNewVersion = currentBaseVersion;
        }
    }

    const handleDeleteConfirm = () => {
        deleteNodeMutation.mutate({
            vaultId: vaultId,
            nodeId: nodeId,
            parentId: currentBaseVersion.parent_id
        });
        setShowDeleteModal(false);
    };

    // Summary Action Handlers
    const handleAddSummary = () => {
        setShowSummary(true);
        setEditSummaryContent('');
        setIsEditingSummary(true);
    };

    const handleEditSummaryClick = () => {
        setEditSummaryContent(currentBaseVersion.ai_summary || '');
        setIsEditingSummary(true);
    };

    const handleCancelSummaryEdit = () => {
        setIsEditingSummary(false);
        // If it was a new summary and we canceled, hide the box
        if (!currentBaseVersion.ai_summary) {
            setShowSummary(false);
        }
    };

    const handleSaveSummary = () => {
        updateSummaryMutation.mutate(editSummaryContent);
    };

    return (
        <>
            {isEditing ? (
                <Alert variant="info">
                    {isViewingOldVersion
                        ? `You are editing content based on version ${currentBaseVersion.version}.`
                        : 'You are editing the current content.'}
                    <br />Saving will create a new, current version.
                </Alert>
            ) : (
                <ContentHeader
                    currentVersion={currentBaseVersion}
                    nodeId={nodeId}
                    vaultId={vaultId}
                    isEditing={isEditing}
                    onEditClick={handleEditClick}
                    onDeleteClick={() => setShowDeleteModal(true)}
                    showSummary={showSummary}
                    onToggleSummary={() => setShowSummary(!showSummary)}
                    onAddSummary={handleAddSummary}
                />
            )}
            <hr />

            {/* AI Summary Collapse Block */}
            {!isEditing && (currentBaseVersion?.ai_summary || showSummary) && (
                <Collapse in={showSummary}>
                    <div id="ai-summary-collapse" className="mb-4">
                        <div className="p-3 bg-light border border-info rounded text-dark shadow-sm" style={{ fontSize: '0.95rem' }}>

                            <div className="fw-bold mb-2 text-info d-flex align-items-center justify-content-between">
                                <div><i className="bx bx-brain me-1"></i> AI Summary</div>
                                {!isEditingSummary && (
                                    <Button variant="link" size="sm" className="p-0 text-info text-decoration-none" onClick={handleEditSummaryClick}>
                                        <i className="bx bx-pencil"></i> Edit
                                    </Button>
                                )}
                            </div>

                            {isEditingSummary ? (
                                <div>
                                    <Form.Control
                                        as="textarea"
                                        rows={4}
                                        value={editSummaryContent}
                                        onChange={(e) => setEditSummaryContent(e.target.value)}
                                        placeholder="Write or edit the AI summary here..."
                                        disabled={updateSummaryMutation.isPending}
                                    />
                                    <div className="d-flex justify-content-end mt-2">
                                        <Button variant="secondary" size="sm" className="me-2" onClick={handleCancelSummaryEdit} disabled={updateSummaryMutation.isPending}>
                                            Cancel
                                        </Button>
                                        <Button variant="info" size="sm" onClick={handleSaveSummary} disabled={updateSummaryMutation.isPending}>
                                            {updateSummaryMutation.isPending ? 'Saving...' : 'Save'}
                                        </Button>
                                    </div>
                                </div>
                            ) : (
                                <>
                                    <div style={{ whiteSpace: 'pre-wrap' }}>
                                        {currentBaseVersion.ai_summary}
                                    </div>
                                    {!currentBaseVersion.summary_is_current && (
                                        <div className="text-warning mt-2" style={{ fontSize: '0.85rem' }}>
                                            <i className="bx bx-error-circle me-1"></i>
                                            Note: This summary might be outdated.
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </Collapse>
            )}

            {isEditing ? (
                <>
                    <NodeEditor content={localContent} onContentChange={setLocalContent} />
                    <div className="d-flex justify-content-end mt-3">
                        <Button variant="secondary" onClick={() => setIsEditing(false)} className="me-2" disabled={isSaving}>Cancel</Button>
                        <Button variant="primary" onClick={() => saveContentMutation.mutate({ nodeId, title: currentBaseVersion.title, content: localContent })} disabled={isSaving}>
                            {isSaving ? 'Saving...' : 'Save as new version'}
                        </Button>
                    </div>
                </>
            ) : sortedNewVersion ? (
                <DiffViewer
                    oldContent={sortedOldVersion?.content || ''}
                    newContent={sortedNewVersion?.content || ''}
                    oldTitle={`v${sortedOldVersion?.version}: ${new Date(sortedOldVersion.timestamp).toLocaleString('en-US')}`}
                    newTitle={`v${sortedNewVersion?.version}: ${new Date(sortedNewVersion.timestamp).toLocaleString('en-US')}`}
                />
            ) : (
                <div className="markdown-body">
                    <MarkdownRenderer content={currentBaseVersion.content || ''} />
                </div>
            )}

            <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)}>
                <Modal.Header closeButton>
                    <Modal.Title>Delete Document</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    Are you sure you want to permanently delete "<strong>{currentBaseVersion.title}</strong>"?
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowDeleteModal(false)} disabled={deleteNodeMutation.isPending}>Cancel</Button>
                    <Button variant="danger" onClick={handleDeleteConfirm} disabled={deleteNodeMutation.isPending}>
                        {deleteNodeMutation.isPending ? 'Deleting...' : 'Permanently delete'}
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}