import React, { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';

// API & Context
import api from '../api/axios';
import { useAppContext } from '../context/AppContext';

// Layout & UI Komponenten
import MainLayout from '../components/layout/MainLayout';
import ContentArea from '../components/nodes/ContentArea';

// Lazy-loaded Komponenten
const PrintPreview = lazy(() => import('../components/print/PrintPreview'));
const DeleteNodeModal = lazy(() => import('../components/common/DeleteNodeModal'));
const VersionHistory = lazy(() => import('../../features/nodes/ui/VersionHistory.jsx'));
const ContextPanel = lazy(() => import('../components/context/ContextPanel'));

export default function NodesView() {
    const { nodeId, vaultId } = useParams();
    const navigate = useNavigate();

    // --- Globaler State (unverändert) ---
    const {
        treeData,
        setTreeDataForContext,
        isPrintPreviewActive,
        isLoadingVaults
    } = useAppContext();

    // --- Lokaler State ---
    const [currentNode, setCurrentNode] = useState(null);
    const [isLoadingNode, setIsLoadingNode] = useState(true);
    const [error, setError] = useState(null);
    const [successMessage, setSuccessMessage] = useState('');
    const [nodeToDelete, setNodeToDelete] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editableContent, setEditableContent] = useState('');
    const [diffSelection, setDiffSelection] = useState({ base: null, compare: null });

    // NEU: States für das Lazy-Loading der Versionen
    const [versions, setVersions] = useState(null); // null: nicht geladen, []: geladen & leer, [...]: geladen
    const [isLoadingVersions, setIsLoadingVersions] = useState(false);


    // ========================================================================
    // DATEN-LADE-EFFEKTE
    // ========================================================================

    // GEÄNDERT: Dieser Effekt lädt jetzt nur noch den "leichten" Node ohne Versionen
    useEffect(() => {
        if (nodeId && vaultId) {
            // Reset-Logik beim Wechsel des Nodes
            setDiffSelection({ base: null, compare: null });
            setIsEditing(false);
            setVersions(null); // NEU: Versions-Cache für den alten Node zurücksetzen
            setIsLoadingVersions(false);

            setIsLoadingNode(true);
            setError(null);
            const controller = new AbortController();

            // API-Aufruf an den "leichten" Endpunkt
            api.get(`/api/vaults/${vaultId}/nodes/${nodeId}`, { signal: controller.signal })
                .then(response => {
                    // Der 'versions'-Schlüssel existiert in der Antwort nicht mehr
                    setCurrentNode(response.data);
                    setEditableContent(response.data.content || '');
                })
                .catch(err => {
                    if (!controller.signal.aborted) {
                        setError(`Knoten konnte nicht geladen werden.`);
                        setCurrentNode(null);
                    }
                })
                .finally(() => {
                    if (!controller.signal.aborted) setIsLoadingNode(false);
                });

            return () => controller.abort();
        } else {
            setCurrentNode(null);
            setIsLoadingNode(false);
        }
    }, [nodeId, vaultId]);

    useEffect(() => {
        if (successMessage) {
            const timer = setTimeout(() => setSuccessMessage(''), 3000);
            return () => clearTimeout(timer);
        }
    }, [successMessage]);

    // ========================================================================
    // STABILISIERTE HANDLER-FUNKTIONEN
    // ========================================================================

    // Anmerkung: Der `refreshTree`-Aufruf nutzt dank ETag Caching und ist effizient.
    const refreshTree = useCallback(() => {
        if (!vaultId) return;
        api.get(`/api/vaults/${vaultId}/nodes?format=tree`)
            .then(res => setTreeDataForContext(res.data))
            .catch(() => setError("Baum konnte nicht aktualisiert werden."));
    }, [vaultId, setTreeDataForContext]);

    // GEÄNDERT: `updateNodeContent` lädt den Node neu, um Cache-Busting zu erzwingen
    const updateNodeContent = useCallback(async (nodeIdToUpdate, updates) => {
        if (!vaultId) return false;
        try {
            await api.put(`/api/vaults/${vaultId}/nodes/${nodeIdToUpdate}`, updates);
            setSuccessMessage("Node erfolgreich aktualisiert!");

            if (nodeIdToUpdate.toString() === nodeId) {
                // Den Node neu laden, um die aktualisierten Daten (inkl. neuem ETag) zu erhalten
                const nodeResponse = await api.get(`/api/vaults/${vaultId}/nodes/${nodeIdToUpdate}`);
                setCurrentNode(nodeResponse.data);
                setEditableContent(nodeResponse.data.content || '');
                setIsEditing(false);
                // NEU: Setze die geladenen Versionen zurück, da sie veraltet sein könnten
                setVersions(null);
            }
            // Baum auch neu laden, falls sich z.B. der Titel geändert hat
            refreshTree();
            return true;
        } catch (err) {
            setError(err.response?.data?.error || "Node konnte nicht gespeichert werden.");
            return false;
        }
    }, [vaultId, nodeId, refreshTree]);

    const handleNodeClick = useCallback((node) => {
        // KORREKTUR: Neue Navigations-URL
        navigate(`/vaults/${vaultId}/nodes/${node.id}`);
    }, [navigate, vaultId]); // KORREKTUR: Abhängigkeit von vaultId

    const handleLinkClick = useCallback(async (linkText) => {
        if (!vaultId) return;
        try {
            // KORREKTUR: Neue API-Route für die Titelsuche
            const response = await api.get(`/api/vaults/${vaultId}/nodes?title=${encodeURIComponent(linkText.trim())}`);
            // Die API gibt eine Liste zurück, auch bei einem Treffer
            if (response.data && response.data.length > 0) {
                // KORREKTUR: Neue Navigations-URL
                navigate(`/vaults/${vaultId}/nodes/${response.data[0].id}`);
                setError(null);
            } else {
                setError(`Linkziel "${linkText}" nicht gefunden.`);
            }
        } catch (error) {
            setError(error.response?.status === 404 ? `Linkziel "${linkText}" nicht gefunden.` : "Serverfehler beim Folgen des Links.");
        }
    }, [vaultId, navigate]); // KORREKTUR: Abhängigkeit von vaultId

    const handleAddNode = useCallback(async (parentNodeId) => {
        if (!vaultId) return;
        const title = prompt("Titel für den neuen Node eingeben:");
        if (!title || !title.trim()) return;
        try {
            const payload = { title, parent_id: parentNodeId }; // KORREKTUR: vault_id wird nicht mehr benötigt
            // KORREKTUR: Neue API-Route
            const response = await api.post(`/api/vaults/${vaultId}/nodes/`, payload);
            await refreshTree();
            // KORREKTUR: Neue Navigations-URL
            navigate(`/vaults/${vaultId}/nodes/${response.data.id}`);
            setSuccessMessage("Node erfolgreich erstellt!");
        } catch (err) {
            setError("Node konnte nicht erstellt werden.");
        }
    }, [vaultId, refreshTree, navigate]); // KORREKTUR: Abhängigkeit von vaultId


    const handleDeleteNode = useCallback((node) => setNodeToDelete(node), []);

    const cancelDelete = useCallback(() => setNodeToDelete(null), []);

    const executeDelete = useCallback(async () => {
        if (!nodeToDelete || !vaultId) return;
        try {
            // KORREKTUR: Neue API-Route
            await api.delete(`/api/vaults/${vaultId}/nodes/${nodeToDelete.id}`);
            if (nodeId === String(nodeToDelete.id)) {
                // KORREKTUR: Neue Navigations-Logik
                const targetPath = nodeToDelete.parent_id
                    ? `/vaults/${vaultId}/nodes/${nodeToDelete.parent_id}`
                    : `/vaults/${vaultId}`; // Leitet zur Vault-Basis weiter
                navigate(targetPath);
            }
            await refreshTree();
            setSuccessMessage(`Node "${nodeToDelete.title}" wurde erfolgreich gelöscht.`);
        } catch (err) {
            setError("Node konnte nicht gelöscht werden. Möglicherweise hat er noch Kinder.");
        } finally {
            setNodeToDelete(null);
        }
    }, [nodeToDelete, vaultId, nodeId, navigate, refreshTree]); // KORREKTUR: Abhängigkeit von vaultId

    const moveNode = useCallback(async (sourceNode, targetNode) => {
        if (!vaultId) return;
        try {
            // KORREKTUR: Annahme einer neuen API-Route für das Verschieben
            await api.post(`/api/vaults/${vaultId}/nodes/move/`, {
                node_id: sourceNode.id,
                new_parent_id: targetNode.id,
            }); // vault_id wird nicht mehr im Body benötigt
            await refreshTree();
        } catch (err) {
            setError(err.response?.data?.error || "Node konnte nicht verschoben werden.");
            await refreshTree();
        }
    }, [vaultId, refreshTree]); // KORREKTUR: Abhängigkeit von vaultId

    const handleSave = useCallback(async () => {
        if (!currentNode) return;
        await updateNodeContent(currentNode.id, { content: editableContent });
    }, [currentNode, editableContent, updateNodeContent]);

    const handleRename = useCallback(async (nodeId, newTitle) => {
        await updateNodeContent(nodeId, { title: newTitle });
    }, [updateNodeContent]);

    // --- ZENTRALE HANDLER FÜR DIE VERSIONSKONTROLLE ---
    const handleLoadVersions = useCallback(() => {
        if (versions || isLoadingVersions || !nodeId || !vaultId) return;

        setIsLoadingVersions(true);
        setError(null);

        api.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`)
            .then(response => {
                setVersions(response.data || []);
            })
            .catch(err => {
                setError("Versionsverlauf konnte nicht geladen werden.");
                setVersions(null); // Bei Fehler zurücksetzen
            })
            .finally(() => setIsLoadingVersions(false));
    }, [versions, isLoadingVersions, nodeId, vaultId]);

    const handleSelectVersion = useCallback((version) => {
        setIsEditing(false);
        setDiffSelection(prev => prev.base?.timestamp === version.timestamp ? { base: null, compare: null } : { base: version, compare: null });
    }, []);

    const handleCompareVersion = useCallback((version) => {
        setIsEditing(false);
        setDiffSelection(prev => !prev.base ? prev : { base: prev.base, compare: version });
    }, []);

    const handleShowCurrentVersion = useCallback(() => {
        setIsEditing(false);
        setDiffSelection({ base: null, compare: null });
    }, []);

    const handleCancelEdit = useCallback(() => {
        setIsEditing(false);
        const originalContent = diffSelection.base ? diffSelection.base.content : (currentNode?.content || '');
        setEditableContent(originalContent);
    }, [diffSelection, currentNode]);

    // ========================================================================
    // MEMOISIERTE KOMPONENTEN-PROPS
    // ========================================================================

    const mainContentComponent = useMemo(() => (
        <ContentArea
            node={currentNode}
            onSave={handleSave}
            onRename={handleRename}
            onLinkClick={handleLinkClick}
            successMessage={successMessage}
            isEditing={isEditing}
            onSetIsEditing={setIsEditing}
            editableContent={editableContent}
            onContentChange={setEditableContent}
            onCancelEdit={handleCancelEdit}
            contentToDisplay={diffSelection.base ? diffSelection.base.content : (currentNode?.content || '')}
            versionForDiffBase={diffSelection.base}
            versionForDiffCompare={diffSelection.compare}
            onShowCurrent={handleShowCurrentVersion}
        />
    ), [
        currentNode, handleSave, handleRename, handleLinkClick, successMessage,
        isEditing, editableContent, handleCancelEdit, diffSelection, handleShowCurrentVersion
    ]);

    const versionHistoryComponent = useMemo(() => {
        // Diese Komponente wird jetzt in einem Offcanvas (Seitenleiste) angezeigt,
        // das vom WorkspaceLayout gesteuert wird. Ihre einzige Aufgabe ist es, den
        // aktuellen Zustand des Ladevorgangs darzustellen.

        return (
            <Suspense fallback={<div className="p-2 text-center small">Lade Komponenten...</div>}>

                {/* Fall 1: Der Ladevorgang für die Versionen läuft gerade. */}
                {isLoadingVersions && (
                    <div className="p-3 text-center small">
                        <div className="spinner-border spinner-border-sm me-2" role="status">
                            <span className="visually-hidden">Loading...</span>
                        </div>
                        Lade Verlauf...
                    </div>
                )}

                {/* Fall 2: Die Versionen sind erfolgreich geladen (versions ist ein Array). */}
                {/* Wichtig: `versions` ist `null`, bis die Daten geladen sind. */}
                {versions && (
                    <VersionHistory
                        versions={versions}
                        diffSelection={diffSelection}
                        onSelectVersion={handleSelectVersion}
                        onCompareVersion={handleCompareVersion}
                        onShowCurrent={handleShowCurrentVersion}
                    />
                )}

                {/* Fall 3 (implizit): Wenn weder geladen wird noch Daten da sind, wird nichts
                angezeigt. Das ist korrekt, da das Offcanvas in diesem Zustand
                entweder geschlossen ist oder der Ladevorgang sofort startet,
                sobald es geöffnet wird. */}

            </Suspense>
        );
    }, [
        // Die Abhängigkeitsliste ist jetzt viel sauberer.
        // Sie hängt nur noch vom Ladezustand und den geladenen Daten ab.
        isLoadingVersions,
        versions,
        diffSelection,
        handleSelectVersion,
        handleCompareVersion,
        handleShowCurrentVersion
    ]);
    
    const contextPanelComponent = useMemo(() => (
        <Suspense fallback={<div className="p-2 text-center small">Lade...</div>}>
            <ContextPanel onNodeUpdate={updateNodeContent} />
        </Suspense>
    ), [updateNodeContent]);

    // ========================================================================
    // RENDER LOGIC
    // ========================================================================
    
    if (isLoadingVaults) return <div className="p-5 text-center">Lade App-Konfiguration...</div>;
    if (!vaultId) return <div className="p-5 text-center">Bitte einen Vault auswählen, um zu starten.</div>;

    if (isPrintPreviewActive) {
		return <Suspense fallback={<div>Lade Druckvorschau...</div>}><PrintPreview onLinkClick={handleLinkClick} /></Suspense>;
	}

    const renderMainContent = () => {
        if (isLoadingNode) return <div className="p-5 text-center">Lade Node...</div>;
        if (error) return <div className="p-5 text-center text-danger">{error}</div>;
        return mainContentComponent;
    }

    return (
        <DndProvider backend={HTML5Backend}>
            <MainLayout
                treeData={treeData}
                activeNodeId={nodeId}
                onNodeClick={handleNodeClick}
                onAddNode={handleAddNode}
                onDeleteNode={handleDeleteNode}
                onMoveNode={moveNode}
                onNodeUpdate={updateNodeContent}
                mainContent={renderMainContent()}
                versionHistory={versionHistoryComponent}
                contextPanel={contextPanelComponent}
                onLoadVersions={handleLoadVersions}
                areVersionsLoaded={versions !== null}
            />
            {nodeToDelete && (
                <Suspense fallback={null}>
                    <DeleteNodeModal node={nodeToDelete} onConfirm={executeDelete} onCancel={cancelDelete}/>
                </Suspense>
            )}
        </DndProvider>
    );
}