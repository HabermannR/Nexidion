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
    // KORREKTUR: Wir nennen die Setter um, um Verwechslungen zu vermeiden
    const setStoreDiffBase = useWorkspaceStore((state) => state.setDiffBase);
    const clearStoreDiff = useWorkspaceStore((state) => state.clearDiff); // Eine dedizierte "Aufräum"-Aktion ist sauberer
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
    useEffect(() => {
        // Wenn sich die nodeId ändert, MÜSSEN wir den alten Zustand verwerfen.
        // `clearDiff` sollte im Store `diffSelection: { base: null, compare: null }` setzen.
        clearStoreDiff();
    }, [nodeId, clearStoreDiff]);
    // =======================================

    // Dieser Effekt berechnet nur noch den Breadcrumb.
    useEffect(() => {
        if (vaultTreeData?.tree && nodeId) {
            const path = findPathInTree(vaultTreeData.tree, nodeId);
            setBreadcrumbPath(path || []);
        } else {
            setBreadcrumbPath([]);
        }
    }, [vaultTreeData, nodeId, setBreadcrumbPath]);

    // Dieser Effekt setzt den initialen Zustand, NACHDEM er zurückgesetzt wurde.
    useEffect(() => {
        if (versions && versions.length > 0) {
            const href = window.location.href;
            const versionParam = new URL(href).searchParams.get('version');
            const initialBase = versionParam
                ? versions.find(v => String(v.version) === versionParam)
                : versions[0];

            // Die fehlerhafte Bedingung `!selectedBaseVersion` ist entfernt.
            if (initialBase) {
                setStoreDiffBase(initialBase);
            }
        }
    }, [versions, setStoreDiffBase]);

    // Dieser Effekt reagiert auf jede Änderung der anzuzeigenden Version.
    useEffect(() => {
        if (selectedBaseVersion) {
            setLocalContent(selectedBaseVersion.content || '');
            setIsEditing(false);
        }
    }, [selectedBaseVersion]);

    // ==========================================================
    // --- PHASE 3: GUARD CLAUSES & BEDINGTE RETURNS ---
    // ==========================================================
    if (!nodeId) {
        return <div className="p-4 text-center text-muted"><h4>Dokument auswählen</h4><p>Wähle ein Dokument aus der Navigation, um es hier anzuzeigen.</p></div>;
    }

    if (isTreeLoading || isLoadingVersions) {
        return <AppLoading message="Lade Dokument..." />;
    }

    if (isTreeError || isVersionsError) {
        return <Alert variant="danger" className="m-4"><h4>Fehler</h4><p>Das Dokument konnte nicht geladen werden.</p></Alert>;
    }

    // ==========================================================
    // --- PHASE 4: VARIABLEN & DATEN FÜR RENDER-LOGIK ---
    // ==========================================================
    const initialVersion = (versions && versions.length > 0) ? versions[0] : null;

    // Wir bestimmen, welche Version angezeigt wird: die vom User ausgewählte oder die initiale.
    const currentBaseVersion = selectedBaseVersion || initialVersion;

    // Prüfe, ob wir nach allen Lade- und Fehlerprüfungen immer noch nichts zum Anzeigen haben.
    if (!currentBaseVersion) {
        return (
            <Alert variant="warning" className="m-4">
                <h4>Kein Inhalt</h4>
                <p>Für dieses Dokument wurde noch kein Inhalt gefunden. Beginne mit dem Bearbeiten, um die erste Version zu erstellen.</p>
            </Alert>
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
                    onEditClick={() => setIsEditing(true)}
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
                <MarkdownRenderer content={currentBaseVersion.content || ''} />
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