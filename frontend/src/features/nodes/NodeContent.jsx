// src/features/nodes/NodeContent.jsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Alert } from 'react-bootstrap';

import apiClient from '../../api/apiClient.js';
import DiffViewer from '../../components/DiffViewer.jsx';

import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useVaultTreeQuery } from './hooks/useVaultTreeQuery.js';
import { useSaveNodeContent } from './hooks/useSaveNodeContent.js';

import ContentHeader from './ContentHeader.jsx';
import NodeEditor from './NodeEditor.jsx';
import MarkdownRenderer from './MarkdownRenderer.jsx';
import AppLoading from '../../components/AppLoading.jsx';

// Hilfsfunktion bleibt unverändert.
const findPathInTree = (nodes, nodeId, currentPath = []) => {
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
    // ==========================================================
    // --- PHASE 1: ALLE HOOKS AUFRUFEN ---
    // ==========================================================
    const { vaultId, nodeId } = useParams();
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    // DATENQUELLEN
    const { data: vaultTreeData, isLoading: isTreeLoading, isError: isTreeError } = useVaultTreeQuery(vaultId);
    const { data: versions, isLoading: isLoadingVersions, isError: isVersionsError } = useQuery({
        queryKey: ['versions', vaultId, nodeId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`).then(res => res.data),
        enabled: !!nodeId,
    });

    // ZUSTAND
    const setBreadcrumbPath = useWorkspaceStore((state) => state.setBreadcrumbPath);
    const setStoreDiffBase = useWorkspaceStore((state) => state.setDiffBase);
    const clearStoreDiff = useWorkspaceStore((state) => state.clearDiff);
    const { base: selectedBaseVersion, compare: selectedCompareVersion } = useWorkspaceStore(state => state.diffSelection);

    const [isEditing, setIsEditing] = useState(false);
    const [localContent, setLocalContent] = useState('');
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const saveContentMutation = useSaveNodeContent({ onSuccess: () => setIsEditing(false) });
    const deleteNodeMutation = useMutation({
        mutationFn: (payload) => apiClient.delete(`/api/vaults/${payload.vaultId}/nodes/${payload.nodeId}`),
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ['vaultTree', variables.vaultId] });
            navigate(variables.parentId ? `/vaults/${variables.vaultId}/nodes/${variables.parentId}` : `/vaults/${variables.vaultId}`);
        },
    });

    // ==========================================================
    // --- PHASE 2: DATEN-SYNCHRONISATION & EFFEKTE ---
    // ==========================================================

    // =======================================
    // === THE FIX IS HERE ===
    // This effect acts as a "master reset" whenever the user navigates to a new node.
    // It runs IMMEDIATELY when `nodeId` changes, before any data fetching completes.
    useEffect(() => {
        // We MUST proactively reset all local and global state related to the
        // node's content to prevent showing stale data from the previous node.
        setIsEditing(false);      // Exit editing mode if it was active on the old node.
        setLocalContent('');      // CRUCIAL: Clear the local editor content immediately.
        clearStoreDiff();         // Clear the globally selected version object in Zustand.

    }, [nodeId, clearStoreDiff]); // The dependency array ensures this runs only on a node change.
    // =======================================

    // This effect calculates the breadcrumb path. It's fine as is.
    useEffect(() => {
        if (vaultTreeData?.tree && nodeId) {
            const path = findPathInTree(vaultTreeData.tree, nodeId);
            setBreadcrumbPath(path || []);
        } else {
            setBreadcrumbPath([]);
        }
    }, [vaultTreeData, nodeId, setBreadcrumbPath]);

    // This effect sets the initial state AFTER the reset has happened and AFTER data has loaded.
    useEffect(() => {
        if (versions && versions.length > 0) {
            const href = window.location.href;
            const versionParam = new URL(href).searchParams.get('version');
            const initialBase = versionParam
                ? versions.find(v => String(v.version) === versionParam)
                : versions[0];

            if (initialBase) {
                setStoreDiffBase(initialBase);
            }
        }
    }, [versions, setStoreDiffBase]);

    // This effect syncs the local editor content with the selected version from global state.
    useEffect(() => {
        // This will only run after the global state (`selectedBaseVersion`) has been correctly
        // set by the effect above, ensuring we don't load stale content.
        if (selectedBaseVersion) {
            setLocalContent(selectedBaseVersion.content || '');
        }
    }, [selectedBaseVersion]);

    // ==========================================================
    // --- PHASE 3: GUARD CLAUSES & BEDINGTE RETURNS ---
    // ==========================================================
    if (!nodeId) {
        return <div className="p-4 text-center text-muted"><h4>Dokument auswählen</h4><p>Wähle ein Dokument aus der Navigation, um es hier anzuzeigen.</p></div>;
    }

    // This loading state is now safe because all stale state has been cleared.
    if (isTreeLoading || isLoadingVersions) {
        return <AppLoading message="Lade Dokument..." />;
    }

    if (isTreeError || isVersionsError) {
        return <Alert variant="danger" className="m-4"><h4>Fehler</h4><p>Das Dokument konnte nicht geladen werden.</p></Alert>;
    }

    // ==========================================================
    // --- PHASE 4: VARIABLEN & DATEN FÜR RENDER-LOGIK ---
    // ==========================================================
    const currentBaseVersion = selectedBaseVersion || (versions && versions.length > 0 ? versions[0] : null);

    const handleEditClick = () => {
        // When the user clicks edit, we know `currentBaseVersion` is stable and correct.
        // We populate the local editor state from it right before entering editing mode.
        setLocalContent(currentBaseVersion?.content || '');
        setIsEditing(true);
    };

    // This check is now robust. If there are no versions, currentBaseVersion will be null.
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

    const isSaving = saveContentMutation.isPending;
    const isViewingOldVersion = currentBaseVersion.id !== versions[0]?.id;

    let sortedOldVersion = currentBaseVersion;
    let sortedNewVersion = selectedCompareVersion;
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

    // ==========================================================
    // --- PHASE 5: FINALES RETURN MIT JSX ---
    // ==========================================================
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
                />
            )}
            <hr />
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