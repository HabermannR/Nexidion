// src/features/workspace/center-panel/NodeContent.jsx

import React, { useState, useEffect } from 'react';
import { useLoaderData, useOutletContext, useFetcher, useParams, useSearchParams, useNavigation } from 'react-router-dom';
import { Button, Modal, Form as BootstrapForm, Alert } from 'react-bootstrap';
import ReactDiffViewer from 'react-diff-viewer-continued';

import { useWorkspaceStore } from '../workspaceStore';
import ContentHeader from './ContentHeader.jsx';
import NodeEditor from './NodeEditor.jsx';
import MarkdownRenderer from './MarkdownRenderer.jsx';

// Die Hilfsfunktion kann außerhalb der Komponente, da sie keinen Zustand benötigt.
const findPathInTree = (nodes, nodeId, currentPath = []) => {
    for (const node of nodes) {
        const newPath = [
            ...currentPath,
            {
                id: node.id,
                title: node.title,
                to: `/vaults/${node.vault_id}/nodes/${node.id}`,
            },
        ];

        if (node.id === nodeId) {
            return newPath;
        }

        if (node.children && node.children.length > 0) {
            const foundPath = findPathInTree(node.children, nodeId, newPath);
            if (foundPath) {
                return foundPath;
            }
        }
    }
    return null;
};

export default function NodeContent() {
    // --- Hooks ---
    const { versions } = useLoaderData();
    const { vaultId, nodeId } = useParams();
    const [searchParams] = useSearchParams();
    const { setBreadcrumbPath, treeData } = useOutletContext();
    const navigation = useNavigation();
    const fetcher = useFetcher();

    // --- Store Actions & Data ---
    const setActiveNodeVersions = useWorkspaceStore(state => state.setActiveNodeVersions);
    const syncDiffSelectionFromUrl = useWorkspaceStore(state => state.syncDiffSelectionFromUrl);
    const { base: baseVersionData, compare: compareVersionData } = useWorkspaceStore(state => state.diffSelection);
    const latestVersionId = useWorkspaceStore(state => state.activeNodeVersions?.[0]?.id);

    // --- Lokaler UI Zustand ---
    const [isEditing, setIsEditing] = useState(false);
    const [localContent, setLocalContent] = useState('');
    const [showRenameModal, setShowRenameModal] = useState(false);
    const [showDeleteModal, setShowDeleteModal] = useState(false);


    // ==========================================================
    // --- DATEN-SYNCHRONISATION & UI-UPDATES ---
    // ==========================================================

    useEffect(() => {
        if (treeData && nodeId) {
            const path = findPathInTree(treeData, nodeId);
            setBreadcrumbPath(path || []);
        } else {
            setBreadcrumbPath([]);
        }
    }, [treeData, nodeId, setBreadcrumbPath]);

    useEffect(() => {
        setActiveNodeVersions(versions);
        const versionNumber = searchParams.get('version');
        const compareNumber = searchParams.get('compare');
        syncDiffSelectionFromUrl(versionNumber, compareNumber);
    }, [versions, searchParams, setActiveNodeVersions, syncDiffSelectionFromUrl]);

    useEffect(() => {
        if (baseVersionData) {
            setLocalContent(baseVersionData.content || '');
            setIsEditing(false);
        }
    }, [baseVersionData]);


    // ==========================================================
    // --- HANDLER FÜR UI-AKTIONEN ---
    // ==========================================================

    const handleSave = () => {
        fetcher.submit(
            { intent: 'updateContent', content: localContent, title: baseVersionData.title },
            { method: 'post' }
        );
        setIsEditing(false);
    };

    const handleCancel = () => {
        setLocalContent(baseVersionData?.content || '');
        setIsEditing(false);
    };

    const handleRenameConfirm = (event) => {
        event.preventDefault();
        const formData = new FormData(event.target);
        formData.append('content', baseVersionData.content || '');
        fetcher.submit(formData, { method: 'post' });
        setShowRenameModal(false);
    };

    // HIER IST DIE KORREKTUR
    const handleDeleteConfirm = () => {
        // Wir erstellen ein Payload-Objekt, das sowohl den Intent als auch die parentId enthält.
        // baseVersionData enthält alle Infos zum Node, auch die parent_id.
        // `|| ''` ist eine Sicherheit, falls parent_id null ist (bei Top-Level-Nodes).
        const payload = {
            intent: 'deleteNode',
            parentId: baseVersionData.parent_id || ''
        };

        fetcher.submit(payload, { method: 'post' });
        setShowDeleteModal(false);
    };


    // ==========================================================
    // --- RENDER-LOGIK & DATENVORBEREITUNG ---
    // ==========================================================

    if (navigation.state === 'loading' && navigation.location.pathname.includes(nodeId)) {
        return <p className="p-4">Lädt Dokument...</p>;
    }

    if (!baseVersionData) {
        return <p className="p-4">Dokument wird initialisiert...</p>;
    }

    const isSaving = fetcher.state === 'submitting';
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
            ) : isViewingOldVersion || compareVersionData ? (
                <ContentHeader
                    currentVersion={baseVersionData}
                    vaultId={vaultId}
                    isEditing={false}
                    onEditClick={() => setIsEditing(true)}
                    onRenameClick={() => setShowRenameModal(true)}
                    onDeleteClick={() => setShowDeleteModal(true)}
                    hideRenameDelete={true}
                />
            ) : (
                <ContentHeader
                    currentVersion={baseVersionData}
                    vaultId={vaultId}
                    isEditing={isEditing}
                    onEditClick={() => setIsEditing(true)}
                    onRenameClick={() => setShowRenameModal(true)}
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
                <ReactDiffViewer
                    oldValue={sortedOldVersion?.content || ''}
                    newValue={sortedNewVersion?.content || ''}
                    splitView={true}
                    leftTitle={`v${sortedOldVersion?.version}: ${new Date(sortedOldVersion.timestamp).toLocaleString('de-DE')}`}
                    rightTitle={`v${sortedNewVersion?.version}: ${new Date(sortedNewVersion.timestamp).toLocaleString('de-DE')}`}
                    useDarkTheme={false}
                />
            ) : (
                <MarkdownRenderer content={baseVersionData.content || ''} />
            )}

            {/* Modals (bleiben unverändert) */}
            <Modal show={showRenameModal} onHide={() => setShowRenameModal(false)}>
                <BootstrapForm onSubmit={handleRenameConfirm}>
                    <Modal.Header closeButton>
                        <Modal.Title>Dokument umbenennen</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <BootstrapForm.Group>
                            <BootstrapForm.Label>Neuer Titel</BootstrapForm.Label>
                            <input type="hidden" name="intent" value="renameNode" />
                            <BootstrapForm.Control name="title" defaultValue={baseVersionData?.title} required autoFocus />
                        </BootstrapForm.Group>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => setShowRenameModal(false)}>Abbrechen</Button>
                        <Button variant="primary" type="submit">Umbenennen</Button>
                    </Modal.Footer>
                </BootstrapForm>
            </Modal>

            <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)}>
                <Modal.Header closeButton>
                    <Modal.Title>Dokument löschen</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    Sind Sie sicher, dass Sie "<strong>{baseVersionData?.title}</strong>" endgültig löschen möchten?
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>Abbrechen</Button>
                    <Button variant="danger" onClick={handleDeleteConfirm}>Endgültig löschen</Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}