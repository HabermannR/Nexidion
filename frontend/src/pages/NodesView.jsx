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
const VersionHistory = lazy(() => import('../components/nodes/VersionHistory'));
const ContextPanel = lazy(() => import('../components/context/ContextPanel'));

export default function NodesView() {
    const { nodeId } = useParams();
    const navigate = useNavigate();
    
    // --- Globaler State ---
    const { 
        treeData,
        setTreeDataForContext, 
        isPrintPreviewActive, 
        activeVault, 
        isLoadingVaults 
    } = useAppContext();
    const activeVaultId = activeVault?.id; // Stabile ID für Abhängigkeiten

    // --- Lokaler State ---
    const [currentNode, setCurrentNode] = useState(null);
    const [isLoadingNode, setIsLoadingNode] = useState(true);
    const [error, setError] = useState(null);
    const [successMessage, setSuccessMessage] = useState('');
    const [nodeToDelete, setNodeToDelete] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editableContent, setEditableContent] = useState('');
    const [diffSelection, setDiffSelection] = useState({ base: null, compare: null });

    // ========================================================================
    // DATEN-LADE-EFFEKTE
    // ========================================================================

    // Effekt 1: Lädt den Projekt-Baum, wenn sich der Vault ändert.
    useEffect(() => {
        if (!activeVaultId) {
            if (treeData.length > 0) setTreeDataForContext([]);
            return;
        }
        const controller = new AbortController();
        api.get('/api/nodes/tree', {
            params: { vault_id: activeVaultId },
            signal: controller.signal,
        })
        .then(res => setTreeDataForContext(res.data))
        .catch(err => {
            if (!controller.signal.aborted) setError("Could not load project tree.");
        });
        return () => controller.abort();
    }, [activeVaultId, setTreeDataForContext]);

    // NEU: Effekt 2: Lädt den Inhalt des aktuellen Nodes, wenn sich die ID in der URL oder der Vault ändert.
    useEffect(() => {
        if (nodeId && activeVaultId) {
            setIsLoadingNode(true);
            setError(null);
            const controller = new AbortController();
            api.get(`/api/nodes/${nodeId}`, {
                params: { vault_id: activeVaultId },
                signal: controller.signal
            })
            .then(response => {
                setCurrentNode(response.data);
                setEditableContent(response.data.content || '');
            })
            .catch(err => {
                if (!controller.signal.aborted) {
                    setError(`Could not load node with ID ${nodeId}.`);
                    setCurrentNode(null);
                }
            })
            .finally(() => {
                if (!controller.signal.aborted) setIsLoadingNode(false);
            });
            return () => controller.abort();
        } else {
            // Wenn keine nodeId da ist, alles zurücksetzen
            setCurrentNode(null);
            setIsLoadingNode(false);
        }
    }, [nodeId, activeVaultId]); // Abhängig von der URL-ID und der Vault-ID

    // Effekt für Erfolgsmeldungen
    useEffect(() => {
        if (successMessage) {
            const timer = setTimeout(() => setSuccessMessage(''), 3000);
            return () => clearTimeout(timer);
        }
    }, [successMessage]);

    // ========================================================================
    // STABILISIERTE HANDLER-FUNKTIONEN (ALLE mit useCallback)
    // ========================================================================

    const refreshTree = useCallback(() => {
        if (!activeVaultId) return;
        api.get('/api/nodes/tree', { params: { vault_id: activeVaultId } })
            .then(res => setTreeDataForContext(res.data))
            .catch(() => setError("Could not update tree."));
    }, [activeVaultId, setTreeDataForContext]);

    const updateNodeContent = useCallback(async (nodeIdToUpdate, updates) => {
        if (!activeVaultId) return false;
        try {
            await api.put(`/api/nodes/${nodeIdToUpdate}`, { ...updates, vault_id: activeVaultId });
            setSuccessMessage("Node updated successfully!");
            if (nodeIdToUpdate.toString() === nodeId) {
                 const nodeResponse = await api.get(`/api/nodes/${nodeIdToUpdate}`, { params: { vault_id: activeVaultId } });
                 setCurrentNode(nodeResponse.data);
                 setEditableContent(nodeResponse.data.content || '');
                 setIsEditing(false);
            }
            refreshTree();
            return true;
        } catch (err) {
            setError(err.response?.data?.error || "Could not save the node.");
            return false;
        }
    }, [activeVaultId, nodeId, refreshTree]);

    const handleNodeClick = useCallback((node) => navigate(`/nodes/${node.id}`), [navigate]);
	
	const handleLinkClick = useCallback(async (linkText) => {
        if (!activeVaultId) return;
        try {
            const response = await api.get(`/api/nodes/${encodeURIComponent(linkText.trim())}`, { 
                params: { vault_id: activeVaultId } 
            });
            if (response.data?.id) {
                navigate(`/nodes/${response.data.id}`);
                setError(null);
            }
        } catch (error) {
            setError(error.response?.status === 404 ? `Link target "${linkText}" not found.` : "Server error following link.");
        }
    }, [activeVaultId, navigate]);

    const handleAddNode = useCallback(async (parentNodeId) => {
        if (!activeVaultId) return;
        const title = prompt("Enter the title for the new node:");
        if (!title || !title.trim()) return;
        try {
            const payload = { title, parent_id: parentNodeId, vault_id: activeVaultId };
            const response = await api.post('/api/nodes', payload);
            await refreshTree();
            navigate(`/nodes/${response.data.id}`);
            setSuccessMessage("Node created successfully!");
        } catch (err) {
            setError("Could not create node.");
        }
    }, [activeVaultId, refreshTree, navigate]);

    const handleDeleteNode = useCallback((node) => setNodeToDelete(node), []);

    const executeDelete = useCallback(async () => {
        if (!nodeToDelete || !activeVaultId) return;
        try {
            await api.delete(`/api/nodes/${nodeToDelete.id}`, { params: { vault_id: activeVaultId } });
            if (nodeId === String(nodeToDelete.id)) {
                navigate(nodeToDelete.parentId ? `/nodes/${nodeToDelete.parentId}` : '/nodes');
            }
            await refreshTree();
            setSuccessMessage(`Node "${nodeToDelete.title}" was successfully deleted.`);
        } catch (err) {
            setError("Could not delete node. It might have children.");
        } finally {
            setNodeToDelete(null);
        }
    }, [nodeToDelete, activeVaultId, nodeId, navigate, refreshTree]);

    const cancelDelete = useCallback(() => setNodeToDelete(null), []);

    const moveNode = useCallback(async (sourceNode, targetNode) => {
		if (!activeVaultId) return;
		try {
			await api.post('/api/nodes/move', { 
				node_id: sourceNode.id,
				new_parent_id: targetNode.id,
				vault_id: activeVaultId
			});
			await refreshTree();
		} catch (err) {
			setError(err.response?.data?.error || "Could not move the node.");
			await refreshTree();
		}
	}, [activeVaultId, refreshTree]);
    
	const handleSave = useCallback(async () => {
		if (!currentNode) return;
		await updateNodeContent(currentNode.id, { content: editableContent });
	}, [currentNode, editableContent, updateNodeContent]);

    const handleRename = useCallback(async (nodeId, newTitle) => {
		await updateNodeContent(nodeId, { title: newTitle });
	}, [updateNodeContent]);

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
        setEditableContent(currentNode?.content || '');
    }, [currentNode]);

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
        />
    ), [
        currentNode, handleSave, handleRename, handleLinkClick, successMessage,
        isEditing, editableContent, handleCancelEdit, diffSelection
    ]);

    const versionHistoryComponent = useMemo(() => (
        <Suspense fallback={<div className="p-2 text-center small">Lade...</div>}>
            <VersionHistory
                versions={currentNode?.versions || []}
                diffSelection={diffSelection}
                onSelectVersion={handleSelectVersion}
                onCompareVersion={handleCompareVersion}
                onShowCurrent={handleShowCurrentVersion}
            />
        </Suspense>
    ), [currentNode?.versions, diffSelection, handleSelectVersion, handleCompareVersion, handleShowCurrentVersion]);
    
    const contextPanelComponent = useMemo(() => (
        <Suspense fallback={<div className="p-2 text-center small">Lade...</div>}>
            <ContextPanel onNodeUpdate={updateNodeContent} />
        </Suspense>
    ), [updateNodeContent]);

    // ========================================================================
    // RENDER LOGIC
    // ========================================================================
    
    if (isLoadingVaults) return <div className="p-5 text-center">Lade App-Konfiguration...</div>;
    if (!activeVaultId) return <div className="p-5 text-center">Bitte einen Vault auswählen, um zu starten.</div>;

    if (isPrintPreviewActive) {
		return <Suspense fallback={<div>Lade Druckvorschau...</div>}><PrintPreview onLinkClick={handleLinkClick} /></Suspense>;
	}

    // Haupt-Ladeanzeige oder Fehler für den Node-Bereich
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
                diffSelection={diffSelection}
                mainContent={renderMainContent()}
                versionHistory={versionHistoryComponent}
                contextPanel={contextPanelComponent}
                // Mobile Callbacks
                onSelectVersionForMobile={handleSelectVersion}
                onCompareVersionForMobile={handleCompareVersion}
                onShowCurrentForMobile={handleShowCurrentVersion}
            />
            {nodeToDelete && (
                <Suspense fallback={null}>
                    <DeleteNodeModal node={nodeToDelete} onConfirm={executeDelete} onCancel={cancelDelete}/>
                </Suspense>
            )}
        </DndProvider>
    );
}