// src/features/nodes/NodeContent.jsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Alert, Collapse } from 'react-bootstrap';

import apiClient from '../../api/apiClient.js';
import DiffViewer from '../../components/DiffViewer.jsx';

import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useVaultTreeQuery } from './hooks/useVaultTreeQuery.js';
import { useSaveNodeContent } from './hooks/useSaveNodeContent.js';

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

    // 1. Hole alle Versionen als schlanke Stubs (Metadaten-Endpunkt)
    const { data: versions, isLoading: isLoadingVersions, isError: isVersionsError } = useQuery({
        queryKey: ['versions', vaultId, nodeId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`).then(res => res.data),
        enabled: !!nodeId,
    });

    // 2. Hole VOLLSTÄNDIGE Daten exklusiv für diese angeforderte Version (oder aktuelle)
    const { data: activeNodeData, isLoading: isLoadingNode, isError: isNodeError } = useQuery({
        queryKey: ['nodeContent', vaultId, nodeId, versionParam],
        queryFn: () => {
            const params = versionParam ? { version: versionParam } : {};
            return apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}`, { params }).then(res => res.data);
        },
        enabled: !!nodeId,
    });

    // 3. Diff-Vergleich falls vom Tab gefordert
    const { data: compareNodeData } = useQuery({
        queryKey: ['nodeContent', vaultId, nodeId, compareParam],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}`, { params: { version: compareParam } }).then(res => res.data),
        enabled: !!compareParam,
    });

    const setBreadcrumbPath = useWorkspaceStore((state) => state.setBreadcrumbPath);

    const [isEditing, setIsEditing] = useState(false);
    const [localContent, setLocalContent] = useState('');
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [showSummary, setShowSummary] = useState(false);

    const saveContentMutation = useSaveNodeContent({
        onSuccess: () => {
            setIsEditing(false);

            // Cache invalidieren, damit die gerade neu erstellte Version
            // sowie die aktualisierte Versionshistorie sofort geladen werden
            queryClient.invalidateQueries({ queryKey: ['nodeContent', vaultId, nodeId] });
            queryClient.invalidateQueries({ queryKey: ['versions', vaultId, nodeId] });

            if (versionParam || compareParam) {
                // Remove ?version and ?compare to see the latest version after save
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
    });

    useEffect(() => {
        setIsEditing(false);
        setLocalContent('');
    }, [nodeId, versionParam]);

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
        return <div className="p-4 text-center text-muted"><h4>Dokument auswählen</h4><p>Wähle ein Dokument aus der Navigation, um es hier anzuzeigen.</p></div>;
    }

    if (isTreeLoading || isLoadingVersions || isLoadingNode) {
        return <AppLoading message="Lade Dokument..." />;
    }

    if (isTreeError || isVersionsError || isNodeError) {
        return <Alert variant="danger" className="m-4"><h4>Fehler</h4><p>Das Dokument konnte nicht geladen werden.</p></Alert>;
    }

    const currentBaseVersion = activeNodeData;

    if (!currentBaseVersion) {
        return (
            <div className="p-4">
                <Alert variant="info">
                    <h4>Kein Inhalt</h4>
                    <p>Für dieses Dokument wurde noch kein Inhalt gefunden. Beginne mit dem Bearbeiten, um die erste Version zu erstellen.</p>
                    <Button variant="primary" onClick={() => setIsEditing(true)}>Bearbeiten</Button>
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

    return (
        <>
            {isEditing ? (
                <Alert variant="info">
                    {isViewingOldVersion
                        ? `Sie bearbeiten Inhalt basierend auf Version ${currentBaseVersion.version}.`
                        : 'Sie bearbeiten den aktuellen Inhalt.'}
                    <br />Beim Speichern wird eine neue, aktuelle Version erstellt.
                </Alert>
            ) : (
                <ContentHeader
                    currentVersion={currentBaseVersion}
                    vaultId={vaultId}
                    isEditing={isEditing}
                    onEditClick={handleEditClick}
                    onDeleteClick={() => setShowDeleteModal(true)}
                    showSummary={showSummary}
                    onToggleSummary={() => setShowSummary(!showSummary)}
                />
            )}
            <hr />

             {!isEditing && currentBaseVersion?.ai_summary && (
                <Collapse in={showSummary}>
                    <div id="ai-summary-collapse" className="mb-4">
                        <div className="p-3 bg-light border border-info rounded text-dark shadow-sm" style={{ fontSize: '0.95rem' }}>
                            <div className="fw-bold mb-1 text-info d-flex align-items-center">
                                <i className="bx bx-brain me-1"></i> AI Zusammenfassung
                            </div>
                            <div style={{ whiteSpace: 'pre-wrap' }}>
                                {currentBaseVersion.ai_summary}
                            </div>
                            {!currentBaseVersion.summary_is_current && (
                                <div className="text-warning mt-2" style={{ fontSize: '0.85rem' }}>
                                    <i className="bx bx-error-circle me-1"></i>
                                    Hinweis: Diese Zusammenfassung ist möglicherweise veraltet.
                                </div>
                            )}
                        </div>
                    </div>
                </Collapse>
            )}

            {isEditing ? (
                <>
                    <NodeEditor content={localContent} onContentChange={setLocalContent} />
                    <div className="d-flex justify-content-end mt-3">
                        <Button variant="secondary" onClick={() => setIsEditing(false)} className="me-2" disabled={isSaving}>Abbrechen</Button>
                        <Button variant="primary" onClick={() => saveContentMutation.mutate({ nodeId, title: currentBaseVersion.title, content: localContent })} disabled={isSaving}>
                            {isSaving ? 'Speichert...' : 'Als neue Version speichern'}
                        </Button>
                    </div>
                </>
            ) : sortedNewVersion ? (
                <DiffViewer
                    oldContent={sortedOldVersion?.content || ''}
                    newContent={sortedNewVersion?.content || ''}
                    oldTitle={`v${sortedOldVersion?.version}: ${new Date(sortedOldVersion.timestamp).toLocaleString('de-DE')}`}
                    newTitle={`v${sortedNewVersion?.version}: ${new Date(sortedNewVersion.timestamp).toLocaleString('de-DE')}`}
                />
            ) : (
                <div className="markdown-body">
                    <MarkdownRenderer content={currentBaseVersion.content || ''} />
                </div>
            )}
            <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)}>
                <Modal.Header closeButton>
                    <Modal.Title>Dokument löschen</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    Sind Sie sicher, dass Sie "<strong>{currentBaseVersion.title}</strong>" endgültig löschen möchten?
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowDeleteModal(false)} disabled={deleteNodeMutation.isPending}>Abbrechen</Button>
                    <Button variant="danger" onClick={handleDeleteConfirm} disabled={deleteNodeMutation.isPending}>
                        {deleteNodeMutation.isPending ? 'Löscht...' : 'Endgültig löschen'}
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}