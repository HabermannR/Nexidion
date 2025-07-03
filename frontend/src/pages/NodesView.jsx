import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import Offcanvas from 'react-bootstrap/Offcanvas';

// API & Context
import api from '../api/axios';
import { useAppContext } from '../context/AppContext';

// Layout & UI Komponenten
import MainLayout from '../components/layout/MainLayout';
import ProjectTree from '../components/nodes/ProjectTree';
import ContentArea from '../components/nodes/ContentArea';
import ContextPanel from '../components/context/ContextPanel';
import DeleteNodeModal from '../components/common/DeleteNodeModal';
import VersionHistory from '../components/nodes/VersionHistory';
import PrintPreview from '../components/print/PrintPreview';
import { renderTextWithLinks } from '../utils/textUtils';
import SecureImage from '../components/common/SecureImage';

export default function NodesView() {
    const { nodeId } = useParams();
    const navigate = useNavigate();
    const { setTreeDataForContext, isPrintPreviewActive, printPreviewData, exitPrintPreview } = useAppContext();

    // ========================================================================
    // #region STATE MANAGEMENT
    // ========================================================================
    const [treeData, setTreeData] = useState([]);
    const [currentNode, setCurrentNode] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [successMessage, setSuccessMessage] = useState('');
    const [nodeToDelete, setNodeToDelete] = useState(null);

    // State für Editor & Versionen, hochgezogen aus ContentArea
    const [isEditing, setIsEditing] = useState(false);
    const [editableContent, setEditableContent] = useState('');
    const [selectedVersion, setSelectedVersion] = useState(null); // null = aktuelle Version

    // State für die mobilen Offcanvas-Panels
    const [showTreePanel, setShowTreePanel] = useState(false);
    const [showContextPanel, setShowContextPanel] = useState(false);
    const [showVersionsPanel, setShowVersionsPanel] = useState(false);
    // ========================================================================
    // #endregion


    // ========================================================================
    // #region DATA FETCHING & SIDE EFFECTS
    // ========================================================================
    const refreshTree = useCallback(async () => {
        try {
            const response = await api.get('/api/nodes/tree');
            setTreeData(response.data);
            setTreeDataForContext(response.data);
        } catch (err) {
            console.error("Failed to refresh tree:", err);
            setError("Could not update the project tree.");
        }
    }, [setTreeDataForContext]);

    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            setError(null);
            setSuccessMessage('');
            try {
                const treePromise = api.get('/api/nodes/tree');

                if (nodeId) {
                    const nodePromise = api.get(`/api/nodes/${nodeId}`);
                    const [treeResponse, nodeResponse] = await Promise.all([treePromise, nodePromise]);
                    setTreeData(treeResponse.data);
                    setTreeDataForContext(treeResponse.data);
                    setCurrentNode(nodeResponse.data);

                    // Zentralen State beim Laden eines Nodes setzen
                    setEditableContent(nodeResponse.data.content || '');
                    setSelectedVersion(null); // Immer zur aktuellen Version zurückkehren
                    setIsEditing(false); // Bearbeitungsmodus zurücksetzen
                } else {
                    const treeResponse = await treePromise;
                    setTreeData(treeResponse.data);
                    setTreeDataForContext(treeResponse.data);
                    setCurrentNode(null);
                }
            } catch (err) {
                console.error("Failed to fetch data:", err);
                setError("Could not load knowledge base. Please try again.");
                setCurrentNode(null);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, [nodeId, setTreeDataForContext]);

    // Timer für Erfolgsmeldungen
    useEffect(() => {
        if (successMessage) {
            const timer = setTimeout(() => setSuccessMessage(''), 3000);
            return () => clearTimeout(timer);
        }
    }, [successMessage]);
    // ========================================================================
    // #endregion


    // ========================================================================
    // #region HANDLER FUNCTIONS (VOLLSTÄNDIG IMPLEMENTIERT)
    // ========================================================================
    const handleNodeClick = (node) => navigate(`/nodes/${node.id}`);
	
	// In your NodesView component, add this function:
	const handleLinkClick = async (linkText) => {
		try {
			const response = await api.get('/api/nodes', { params: { title: linkText.trim() } });
			const results = response.data;
			if (Array.isArray(results) && results.length > 0) {
				const nodeData = results[0];
				if (nodeData && nodeData.id) {
					navigate(`/nodes/${nodeData.id}`);
				} else {
					setError(`Found a node for "${linkText}" but it has an invalid format.`);
				}
			} else {
				setError(`Link target "${linkText}" does not exist.`);
			}
		} catch (error) {
			console.error('Error fetching node by title:', error);
			setError(`Could not follow link to "${linkText}". An error occurred.`);
		}
	};

    const handleResolveAndNavigate = async (linkTitle) => {
        try {
            // API-Endpunkt, der nach einem Node anhand des Titels sucht
            const response = await api.get('/api/nodes', { params: { title: linkTitle.trim() } });
            const results = response.data;
            if (Array.isArray(results) && results.length > 0) {
                const nodeData = results[0];
                if (nodeData && nodeData.id) {
                    navigate(`/nodes/${nodeData.id}`);
                }
            } else {
                setError(`Link target "${linkTitle}" does not exist.`);
            }
        } catch (error) {
            console.error('Error fetching node by title:', error);
            setError(`Could not follow link to "${linkTitle}". An error occurred.`);
        }
    };

    const handleAddNode = async (parentNodeId) => {
        const title = prompt("Enter the title for the new node:");
        if (!title || !title.trim()) return;
        try {
            const response = await api.post('/api/nodes', { title, parent_id: parentNodeId });
            await refreshTree();
            navigate(`/nodes/${response.data.id}`);
            setSuccessMessage("Node created successfully!");
        } catch (err) {
            setError("Could not create node.");
        }
    };

    const handleDeleteNode = (node) => {
        if (node.title === 'IFS Landkarte') {
            alert('This special node cannot be deleted.');
            return;
        }
        setNodeToDelete(node);
    };

    const executeDelete = async () => {
        if (!nodeToDelete) return;
        try {
            await api.delete(`/api/nodes/${nodeToDelete.id}`);
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
    };

    const cancelDelete = () => setNodeToDelete(null);

    const moveNode = async (sourceNode, targetParentNode) => {
        try {
            await api.post('/api/nodes/move', { node_id: sourceNode.id, new_parent_id: targetParentNode.id });
            await refreshTree();
        } catch (err) {
            setError("Could not move the node.");
        }
    };

    const updateNodeContent = useCallback(async (nodeId, newContent) => {
    try {
        // Schritt 1: Finde den aktuellen Titel, bevor wir speichern.
        // Wir suchen im aktuellen State, um eine extra DB-Abfrage zu vermeiden.
        let currentTitle = '';
        if (currentNode && currentNode.id === nodeId) {
            currentTitle = currentNode.title;
        } else {
            // Fallback, falls ein anderer Node als der angezeigte aktualisiert wird
            const findNodeInTree = (nodes, id) => {
                for (const node of nodes) {
                    if (node.id === id) return node;
                    if (node.children) {
                        const found = findNodeInTree(node.children, id);
                        if (found) return found;
                    }
                }
                return null;
            };
            const nodeToUpdate = findNodeInTree(treeData, nodeId);
            if (nodeToUpdate) {
                currentTitle = nodeToUpdate.title;
            } else {
                // Notfall-Fallback
                console.warn("Could not find title for node, fetching from server...");
                const titleResponse = await api.get(`/api/nodes/${nodeId}`);
                currentTitle = titleResponse.data.title;
            }
        }
        
        // Schritt 2: Speichere die Änderungen. Wir ignorieren die Antwort bewusst.
        await api.put(`/api/nodes/${nodeId}`, {
            content: newContent,
            title: currentTitle 
        });

        // Schritt 3: Lade ALLE relevanten Daten neu. Das ist der robusteste Weg.
        // Wir laden den Baum und den spezifischen Node parallel, um Zeit zu sparen.
        const treePromise = refreshTree(); // Lädt den Baum im Hintergrund
        const nodePromise = api.get(`/api/nodes/${nodeId}`); // Holt den EINEN Node frisch

        const [, nodeResponse] = await Promise.all([treePromise, nodePromise]);

        // Schritt 4: Setze den State mit den frisch geladenen, garantiert korrekten Daten.
        const freshNodeData = nodeResponse.data;
        setCurrentNode(freshNodeData);
        setEditableContent(freshNodeData.content);
        setSelectedVersion(null);
        setIsEditing(false);
        setSuccessMessage("Node updated successfully!");
        
        return true;

    } catch (err) {
        console.error("Failed to update node content:", err);
        setError("Could not save the node.");
        return false;
    }
}, [currentNode, treeData, refreshTree]); // `refreshTree` als Abhängigkeit ist wichtig

	const handleSave = async () => {
		if (!currentNode) return;
		await updateNodeContent(currentNode.id, editableContent);
	};

    const handleRename = async (nodeId, newTitle) => {
        try {
            const response = await api.patch(`/api/nodes/${nodeId}/rename`, { title: newTitle });
            // Den aktuellen Node im State aktualisieren
            setCurrentNode(prev => ({ ...prev, title: response.data.title }));
            await refreshTree(); // Den Baum aktualisieren, damit der neue Titel dort erscheint
            setSuccessMessage("Node renamed successfully!");
        } catch (err) {
            setError("Could not rename the node.");
        }
    };

    const handleCancelEdit = () => {
        setIsEditing(false);
        const originalContent = selectedVersion ? selectedVersion.content : (currentNode?.content || '');
        setEditableContent(originalContent);
    };

    const handleVersionClick = (version) => {
        setSelectedVersion(version);
        setEditableContent(version.content);
        setIsEditing(false);
    };

    const handleShowCurrentVersion = () => {
        setSelectedVersion(null);
        setEditableContent(currentNode?.content || '');
    };
    // ========================================================================
    // #endregion


    // ========================================================================
    // #region RENDER LOGIC
    // ========================================================================
    if (isLoading) return <div className="p-5 text-center">Loading Knowledge Base...</div>;
    if (error) return <div className="p-5 text-center text-danger">Error: {error}</div>;
    if (isPrintPreviewActive) {
		return <PrintPreview onLinkClick={handleLinkClick} />;
	}

    const contentToDisplay = selectedVersion ? selectedVersion.content : (currentNode?.content || '');

    return (
        <DndProvider backend={HTML5Backend}>
            <MainLayout
                treeView={
                    <ProjectTree
                        treeData={treeData}
                        activeNodeId={nodeId}
                        onNodeClick={handleNodeClick}
                        onAddNode={handleAddNode}
                        onDeleteNode={handleDeleteNode}
                        onMoveNode={moveNode}
                    />
                }
                mainContent={
                    <ContentArea
                        node={currentNode}
                        onSave={handleSave}
                        onRename={handleRename}
                        onLinkClick={handleResolveAndNavigate}
                        successMessage={successMessage}

                        // Props zur Steuerung von ContentArea
                        isEditing={isEditing}
                        onSetIsEditing={setIsEditing}
                        editableContent={editableContent}
                        onContentChange={setEditableContent}
                        onCancelEdit={handleCancelEdit}
                        contentToDisplay={contentToDisplay}
                    />
                }
                contextPanel={<ContextPanel onNodeUpdate={updateNodeContent} />}
                versionHistory={
                    <VersionHistory
                        versions={currentNode?.versions || []}
                        selectedVersion={selectedVersion}
                        onVersionClick={handleVersionClick}
                        onShowCurrent={handleShowCurrentVersion}
                    />
                }
                onToggleTree={() => setShowTreePanel(true)}
                onToggleContext={() => setShowContextPanel(true)}
                onToggleVersions={() => setShowVersionsPanel(true)}
            />

            {/* Mobile Offcanvas Panels */}
            <Offcanvas show={showTreePanel} onHide={() => setShowTreePanel(false)} placement="start">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>
                    <ProjectTree
                        treeData={treeData}
                        activeNodeId={nodeId}
                        onNodeClick={(node) => { handleNodeClick(node); setShowTreePanel(false); }}
                        onAddNode={handleAddNode}
                        onDeleteNode={handleDeleteNode}
                        onMoveNode={moveNode}
                    />
                </Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showContextPanel} onHide={() => setShowContextPanel(false)} placement="end">
                <Offcanvas.Header closeButton><Offcanvas.Title>Context & Chat</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body><ContextPanel /></Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showVersionsPanel} onHide={() => setShowVersionsPanel(false)} placement="bottom" style={{ height: '75vh' }}>
                <Offcanvas.Header closeButton><Offcanvas.Title>Version History</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>
                    <VersionHistory
                        versions={currentNode?.versions || []}
                        selectedVersion={selectedVersion}
                        onVersionClick={(v) => { handleVersionClick(v); setShowVersionsPanel(false); }}
                        onShowCurrent={() => { handleShowCurrentVersion(); setShowVersionsPanel(false); }}
                    />
                </Offcanvas.Body>
            </Offcanvas>

            {/* Das Modal wird nur gerendert, wenn `nodeToDelete` gesetzt ist */}
            {nodeToDelete && (
                <DeleteNodeModal
                    node={nodeToDelete}
                    onConfirm={executeDelete}
                    onCancel={cancelDelete}
                />
            )}
        </DndProvider>
    );
}