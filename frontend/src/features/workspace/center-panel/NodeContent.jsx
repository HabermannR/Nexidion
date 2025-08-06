// WESENTLICHE ÄNDERUNGEN:
// - useLoaderData, useFetcher, useNavigation entfernt.
// - NEU: useQuery, useMutation, useQueryClient von @tanstack/react-query
// - Datenladung und Mutationen werden direkt in der Komponente verwaltet.

import React, { useState, useEffect } from 'react';
import { useOutletContext, useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Modal, Form as BootstrapForm, Alert } from 'react-bootstrap';

import apiClient from '../../../api/apiClient';
import DiffViewer from '../../../components/DiffViewer.jsx';
import { useWorkspaceStore } from '../workspaceStore';
import ContentHeader from './ContentHeader.jsx';
import NodeEditor from './NodeEditor.jsx';
import MarkdownRenderer from './MarkdownRenderer.jsx';

// Die Hilfsfunktion bleibt unverändert
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
    // --- Hooks (V4-Stil) ---
    const { vaultId, nodeId } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { setBreadcrumbPath, treeData } = useOutletContext();

    // --- Datenladung mit useQuery ---

    const { data: versions, isLoading: isLoadingVersions, isError } = useQuery({
        queryKey: ['versions', vaultId, nodeId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`).then(res => res.data),
        enabled: !!vaultId && !!nodeId, // Query nur ausführen, wenn IDs vorhanden sind
    });

    // --- Store Actions & Data  ---
    const { setDiffBase, clearDiff } = useWorkspaceStore();
    const { base: baseVersionData, compare: compareVersionData } = useWorkspaceStore(state => state.diffSelection);

    // --- Lokaler UI Zustand  ---
    const [isEditing, setIsEditing] = useState(false);
    const [localContent, setLocalContent] = useState('');
    const [showDeleteModal, setShowDeleteModal] = useState(false);


    // ==========================================================
    // --- Mutationen mit useMutation ---
    // ==========================================================

    const saveContentMutation = useMutation({
        mutationFn: (payload) => apiClient.put(`/api/vaults/${vaultId}/nodes/${nodeId}`, payload),
        onSuccess: () => {
            console.log("Inhalt erfolgreich gespeichert.");
            queryClient.invalidateQueries({ queryKey: ['versions', vaultId, nodeId] });
            setIsEditing(false);
        },
        onError: (err) => console.error("Fehler beim Speichern:", err),
    });

    const deleteNodeMutation = useMutation({
        mutationFn: () => apiClient.delete(`/api/vaults/${vaultId}/nodes/${nodeId}`),
        onSuccess: () => {
            console.log("Node erfolgreich gelöscht.");
            // Den Baum invalidieren, damit er sich aktualisiert
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            // Weg navigieren, z.B. zum Parent oder Vault-Root
            const parentId = baseVersionData?.parent_id;
            navigate(parentId ? `/vaults/${vaultId}/nodes/${parentId}` : `/vaults/${vaultId}`);
        },
        onError: (err) => console.error("Fehler beim Löschen:", err),
    });


    // ==========================================================
    // --- DATEN-SYNCHRONISATION & UI-UPDATES (angepasst) ---
    // ==========================================================

    useEffect(() => {
        if (treeData && nodeId) {
            const path = findPathInTree(treeData, nodeId);
            setBreadcrumbPath(path || []);
        } else {
            setBreadcrumbPath([]);
        }
    }, [treeData, nodeId]);

    useEffect(() => {
        if (versions && versions.length > 0) {
            const versionParam = new URL(window.location.href).searchParams.get('version');
            const initialBase = versionParam
                ? versions.find(v => String(v.version) === versionParam)
                : versions[0];

            setDiffBase(initialBase || versions[0]);
        }

        // The cleanup function also uses a stable action, so it's safe.
        return () => {
            clearDiff();
        };
    }, [versions, nodeId]);

    useEffect(() => {
        if (baseVersionData) {
            setLocalContent(baseVersionData.content || '');
            setIsEditing(false);
        }
    }, [baseVersionData]);


    // ==========================================================
    // --- HANDLER FÜR UI-AKTIONEN (angepasst) ---
    // ==========================================================

    const handleSave = () => {
        saveContentMutation.mutate({
            content: localContent,
            title: baseVersionData.title, // Titel mitsenden, wie es die API erwartet
        });
    };

    const handleCancel = () => {
        setLocalContent(baseVersionData?.content || '');
        setIsEditing(false);
    };

    const handleDeleteConfirm = () => {
        deleteNodeMutation.mutate();
        setShowDeleteModal(false);
    };


    // ==========================================================
    // --- RENDER-LOGIK & DATENVORBEREITUNG  ---
    // ==========================================================

    // Ersetzt den navigation.state check
    if (isLoadingVersions) {
        return <p className="p-4">Lädt Dokument...</p>;
    }

    if (isError || !baseVersionData) {
        return <p className="p-4">Dokument konnte nicht geladen werden oder ist nicht vorhanden.</p>;
    }

    const isSaving = saveContentMutation.isPending;
    const latestVersionId = versions?.[0]?.id;
    const isViewingOldVersion = baseVersionData.id !== latestVersionId;

    let sortedOldVersion = baseVersionData;
    let sortedNewVersion = compareVersionData;
    if (compareVersionData && baseVersionData) {
        if ((baseVersionData.version || 0) > (compareVersionData.version || 0)) {
            sortedOldVersion = compareVersionData;
            sortedNewVersion = baseVersionData;
        }
    }

    return (
        <div className="pt-3">
            {isEditing ? (
                <Alert variant="info">
                    {isViewingOldVersion
                        ? `Sie bearbeiten Inhalt basierend auf Version ${baseVersionData.version}.`
                        : 'Sie bearbeiten den aktuellen Inhalt.'}
                    <br/>Beim Speichern wird eine neue, aktuelle Version erstellt.
                </Alert>
            ) : (
                <ContentHeader
                    currentVersion={baseVersionData}
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
                        <Button variant="secondary" onClick={handleCancel} className="me-2" disabled={isSaving}>
                            Abbrechen
                        </Button>
                        <Button variant="primary" onClick={handleSave} disabled={isSaving}>
                            {isSaving ? 'Speichert...' : 'Als neue Version speichern'}
                        </Button>
                    </div>
                </>
            ) : compareVersionData ? (
                <DiffViewer
                    oldContent={sortedOldVersion?.content || ''}
                    newContent={sortedNewVersion?.content || ''}
                    oldTitle={`v${sortedOldVersion?.version}: ${new Date(sortedOldVersion.timestamp).toLocaleString('de-DE')}`}
                    newTitle={`v${sortedNewVersion?.version}: ${new Date(sortedNewVersion.timestamp).toLocaleString('de-DE')}`}
                />
            ) : (
                <MarkdownRenderer content={baseVersionData.content || ''} />
            )}

            <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)}>
                <Modal.Header closeButton>
                    <Modal.Title>Dokument löschen</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    Sind Sie sicher, dass Sie "<strong>{baseVersionData?.title}</strong>" endgültig löschen möchten?
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowDeleteModal(false)} disabled={deleteNodeMutation.isPending}>Abbrechen</Button>
                    <Button variant="danger" onClick={handleDeleteConfirm} disabled={deleteNodeMutation.isPending}>
                        {deleteNodeMutation.isPending ? 'Löscht...' : 'Endgültig löschen'}
                    </Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}