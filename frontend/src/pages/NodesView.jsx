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
    const { setTreeDataForContext, isPrintPreviewActive, activeVault, isLoadingVaults } = useAppContext();

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
    //const [selectedVersion, setSelectedVersion] = useState(null); // null = aktuelle Version
	const [diffSelection, setDiffSelection] = useState({
	  base: null, // Die erste, als Basis ausgewählte Version
	  compare: null // Die zweite, zum Vergleich ausgewählte Version
	});
	
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
        if (!activeVault) return; // Nichts tun, wenn kein Vault aktiv ist
        try {
            const response = await api.get('/api/nodes/tree', {
                params: { vault_id: activeVault.id }
            });
            setTreeData(response.data);
            setTreeDataForContext(response.data);
        } catch (err) {
            console.error("Failed to refresh tree:", err);
            setError("Could not update the project tree.");
        }
    }, [activeVault, setTreeDataForContext]); // activeVault als Abhängigkeit

	useEffect(() => {
		// Guard Clause: Nicht fetchen, wenn noch kein Vault geladen/ausgewählt ist.
		if (!activeVault) {
			setIsLoading(false);
			return;
		}

		// NEUE LOGIK: Prüfe sofort, ob wir eine nodeId haben, die möglicherweise ungültig ist
		if (nodeId) {
			// Prüfe, ob die URL gerade durch einen Vault-Wechsel entstanden ist
			// Wenn ja, navigiere sofort weg ohne API-Call
			const lastVaultId = localStorage.getItem('lastActiveVaultId');
			const currentVaultId = activeVault.id.toString();
			
			if (lastVaultId && lastVaultId !== currentVaultId) {
				// Vault wurde gewechselt - navigiere sofort zur Node-Liste
				localStorage.setItem('lastActiveVaultId', currentVaultId);
				navigate('/nodes', { replace: true });
				return;
			}
		}

		// Speichere die aktuelle Vault-ID für den nächsten Wechsel
		localStorage.setItem('lastActiveVaultId', activeVault.id.toString());

		const abortController = new AbortController();

		const fetchData = async () => {
			setIsLoading(true);
			setError(null);
			setSuccessMessage('');
			
			try {
				const params = { vault_id: activeVault.id };
				const config = { params, signal: abortController.signal };
				
				if (nodeId) {
					const treePromise = api.get('/api/nodes/tree', config);
					const nodePromise = api.get(`/api/nodes/${nodeId}`, config);
					
					try {
						const [treeResponse, nodeResponse] = await Promise.all([treePromise, nodePromise]);
						
						if (abortController.signal.aborted) return;
						
						setTreeData(treeResponse.data);
						setTreeDataForContext(treeResponse.data);
						setCurrentNode(nodeResponse.data);
						setEditableContent(nodeResponse.data.content || '');
						setDiffSelection({ base: null, compare: null }); 
						setIsEditing(false);
						setIsEditing(false);
					} catch (nodeError) {
						if (abortController.signal.aborted) return;
						
						if (nodeError.response?.status === 404) {
							const treeResponse = await treePromise;
							setTreeData(treeResponse.data);
							setTreeDataForContext(treeResponse.data);
							setCurrentNode(null);
							navigate('/nodes', { replace: true });
							return;
						} else {
							throw nodeError;
						}
					}
				} else {
					const treeResponse = await api.get('/api/nodes/tree', config);
					
					if (abortController.signal.aborted) return;
					
					setTreeData(treeResponse.data);
					setTreeDataForContext(treeResponse.data);
					setCurrentNode(null);
				}
			} catch (err) {
				if (abortController.signal.aborted) return;
				
				console.error("Failed to fetch data:", err);
				setError("Could not load knowledge base. Please try again.");
				setCurrentNode(null);
			} finally {
				if (!abortController.signal.aborted) {
					setIsLoading(false);
				}
			}
		};

		fetchData();

		return () => {
			abortController.abort();
		};
	}, [nodeId, activeVault, navigate, setTreeDataForContext]);

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
	
	const handleLinkClick = async (linkText) => {
    if (!activeVault) return;
    try {
        // Wir rufen den neuen, intelligenten Endpunkt auf.
        // Der Titel wird direkt in die URL eingefügt, genau wie eine ID.
        const response = await api.get(`/api/nodes/${encodeURIComponent(linkText.trim())}`, { 
            params: { 
                vault_id: activeVault.id 
            } 
        });

        // Die Antwort ist jetzt direkt das Node-Objekt, keine Liste mehr.
        const nodeData = response.data;

        if (nodeData && nodeData.id) {
            // Da wir schon das volle Node-Objekt haben, können wir direkt dorthin navigieren.
            // React Router wird die Seite neu laden und die Daten aus der URL (die ID) fetchen.
            navigate(`/nodes/${nodeData.id}`);
            setError(null);
        } else {
            // Dies sollte nicht mehr passieren, da das Backend 404 zurückgibt, was der catch-Block fängt.
            setError(`Fehler: Node für "${linkText}" hat ein ungültiges Format.`);
        }
    } catch (error) {
        if (error.response?.status === 404) {
            setError(`Fehler: Der Link-Ziel "${linkText}" existiert nicht.`);
        } else {
            console.error('Error fetching node by title:', error);
            setError(`Konnte dem Link zu "${linkText}" nicht folgen. Ein Serverfehler ist aufgetreten.`);
        }
    }
};


    const handleAddNode = async (parentNodeId) => {
        // VAULT-FIX: vault_id im Payload mitsenden
        if (!activeVault) return;
        const title = prompt("Enter the title for the new node:");
        if (!title || !title.trim()) return;
        try {
            const payload = { 
                title, 
                parent_id: parentNodeId,
                vault_id: activeVault.id 
            };
            const response = await api.post('/api/nodes', payload);
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
        // VAULT-FIX: vault_id als Parameter senden
        if (!nodeToDelete || !activeVault) return;
        try {
            await api.delete(`/api/nodes/${nodeToDelete.id}`, {
                params: { vault_id: activeVault.id }
            });
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

    const moveNode = async (sourceNode, targetNode) => {
		if (!activeVault) return;
		
		try {
			await api.post('/api/nodes/move', { 
				node_id: sourceNode.id,
				new_parent_id: targetNode.id,
				vault_id: activeVault.id 
			});
			await refreshTree();
		} catch (err) {
			console.error("Could not move the node.", err);
			const errorMessage = err.response?.data?.error || "Could not move the node.";
			setError(errorMessage);
			await refreshTree();
		}
	};

    // Ersetzen Sie Ihre alte `updateNodeContent`-Funktion mit dieser kompletten, neuen Version.
	// Sie passt perfekt zur `onNodeUpdate`-Prop-Struktur.

	const updateNodeContent = useCallback(async (nodeId, updates, vaultId) => {
		// Schritt 1: Vault-ID validieren.
		// Nimmt die explizit übergebene vaultId, oder greift auf den aktiven Vault aus dem Kontext zurück.
		const effectiveVaultId = vaultId || activeVault?.id;

		if (!effectiveVaultId) {
			setError("Cannot update node: No active vault ID was provided.");
			console.error("Update aborted: effectiveVaultId is missing.", { vaultId, activeVault });
			return false; // Signalisiert einen Fehler an den Aufrufer (z.B. ActionButtons).
		}

		try {
			// Schritt 2: Payload für den API-Aufruf vorbereiten.
			// Die 'updates' sind ein Objekt, z.B. { content: "neuer Inhalt" } oder { title: "neuer Titel" }.
			// Wir fügen die validierte vault_id hinzu.
			const payload = {
				...updates,
				vault_id: effectiveVaultId
			};
			
			// Schritt 3: API-Aufruf zum Speichern der Änderungen.
			// Der Backend-Endpunkt `/api/nodes/<node_id>` erwartet einen PUT-Request mit diesem Payload.
			await api.put(`/api/nodes/${nodeId}`, payload);

			// Schritt 4: UI synchronisieren.
			// Wir laden die Daten neu, um sicherzustellen, dass die Anzeige (inkl. Versionen) aktuell ist.
			setSuccessMessage("Node updated successfully!");

			// Wenn der aktuell geöffnete Node bearbeitet wurde, laden wir seine Daten direkt neu.
			if (nodeId === currentNode?.id) {
				 const nodeResponse = await api.get(`/api/nodes/${nodeId}`, { 
					 params: { vault_id: effectiveVaultId } 
				 });
				 const freshNodeData = nodeResponse.data;
				 
				 // Den State der Seite mit den frischen Daten aktualisieren.
				 setCurrentNode(freshNodeData);
				 setEditableContent(freshNodeData.content || '');
				 setDiffSelection({ base: null, compare: null }); 
						setIsEditing(false);
				 setIsEditing(false);      // Den Bearbeitungsmodus beenden.
			}
			
			// Unabhängig davon, welcher Node bearbeitet wurde, laden wir den gesamten Baum neu.
			// Das ist wichtig, falls ein Titel geändert wurde, der im Baum angezeigt wird.
			await refreshTree();
			
			// Schritt 5: Erfolg signalisieren.
			return true;

		} catch (err) {
			// Schritt 6: Fehlerbehandlung.
			const errorMessage = err.response?.data?.error || "Could not save the node. Please check the console.";
			console.error("Failed to update node content:", err);
			setError(errorMessage);
			
			// Fehlschlag signalisieren.
			return false;
		}
		// Abhängigkeiten für useCallback: Diese Funktion wird nur neu erstellt, wenn sich
		// einer dieser Werte ändert. Das ist wichtig für die Performance.
	}, [activeVault, currentNode?.id, refreshTree]);

	const handleSave = async () => {
		if (!currentNode) return;

		// KORREKTUR: Wickeln Sie den Inhalt in ein Objekt mit dem Key 'content'
		const updates = { 
			content: editableContent
		};
		
		// Der Aufruf an die zentrale Update-Funktion
		await updateNodeContent(currentNode.id, updates, activeVault.id);
	};

    const handleRename = async (nodeId, newTitle) => {
        // VAULT-FIX: vault_id im Payload mitsenden
        if (!activeVault) return;
        try {
            await api.patch(`/api/nodes/${nodeId}/rename`, { 
                title: newTitle,
                vault_id: activeVault.id 
            });
            // Den aktuellen Node im State aktualisieren
            setCurrentNode(prev => ({ ...prev, title: newTitle }));
            await refreshTree(); // Den Baum aktualisieren, damit der neue Titel dort erscheint
            setSuccessMessage("Node renamed successfully!");
        } catch (err) {
            setError("Could not rename the node.");
        }
    };

    const handleSelectVersion = useCallback((version) => {
        setIsEditing(false);
        setDiffSelection(prev => {
            // Wenn die bereits ausgewählte Basis erneut angeklickt wird, hebe die Auswahl auf.
            if (prev.base?.timestamp === version.timestamp) {
                return { base: null, compare: null };
            }
            // Ansonsten setze die angeklickte Version als neue Basis und lösche den Vergleich.
            return { base: version, compare: null };
        });
    }, []);

    // Dieser Handler wird NUR durch das Diff-Icon aufgerufen.
    // Er setzt die 'compare'-Version für den Diff.
    const handleCompareVersion = useCallback((version) => {
        setIsEditing(false);
        setDiffSelection(prev => {
            // Ein Vergleich ist nur möglich, wenn bereits eine Basis-Version ausgewählt ist.
            if (!prev.base) return prev; 
            
            // Setze die angeklickte Version als Vergleichsziel.
            return { base: prev.base, compare: version };
        });
    }, []);


    const handleShowCurrentVersion = useCallback(() => {
        setIsEditing(false);
        setDiffSelection({ base: null, compare: null });
        setEditableContent(currentNode?.content || '');
    }, [currentNode]);

    const handleCancelEdit = () => {
        setIsEditing(false);
        // Der Inhalt wird zurückgesetzt auf den der 'base'-Version oder den aktuellen Inhalt.
        const originalContent = diffSelection.base ? diffSelection.base.content : (currentNode?.content || '');
        setEditableContent(originalContent);
    };
    // ========================================================================
    // #endregion


    // ========================================================================
    // #region RENDER LOGIC
    // ========================================================================
    if (isLoadingVaults) return <div className="p-5 text-center">Lade Vaults...</div>;
    if (!activeVault) return <div className="p-5 text-center">Bitte wählen Sie einen Vault aus.</div>;
    if (isLoading) return <div className="p-5 text-center">Lade Node-Daten...</div>;
    if (error) return <div className="p-5 text-center text-danger">Error: {error}</div>;
    if (isPrintPreviewActive) {
		return <PrintPreview onLinkClick={handleLinkClick} />;
	}

    const contentToDisplay = diffSelection.base ? diffSelection.base.content : (currentNode?.content || '');

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
                        onLinkClick={handleLinkClick}
                        successMessage={successMessage}

                        // Props zur Steuerung von ContentArea
                        isEditing={isEditing}
                        onSetIsEditing={setIsEditing}
                        editableContent={editableContent}
                        onContentChange={setEditableContent}
                        onCancelEdit={handleCancelEdit}
                        contentToDisplay={contentToDisplay}
						versionForDiffBase={diffSelection.base}
                        versionForDiffCompare={diffSelection.compare}
                    />
                }
                contextPanel={<ContextPanel onNodeUpdate={updateNodeContent} />}
                versionHistory={
                    <VersionHistory
                        versions={currentNode?.versions || []}
                        diffSelection={diffSelection}
                        // GEÄNDERT: Die neuen, spezifischen Handler übergeben
                        onSelectVersion={handleSelectVersion}
                        onCompareVersion={handleCompareVersion}
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
                        diffSelection={diffSelection}
                        // GEÄNDERT: Auch hier die neuen Handler übergeben
                        onSelectVersion={(v) => {
                            // Beim Auswählen einer Basis-Version im Mobile-View, das Fenster noch offen lassen.
                            handleSelectVersion(v);
                        }}
                        onCompareVersion={(v) => {
                            // Sobald eine Version zum Vergleich ausgewählt wird, schließt sich das Fenster.
                            handleCompareVersion(v);
                            setShowVersionsPanel(false);
                        }}
                        onShowCurrent={() => { 
                            handleShowCurrentVersion(); 
                            setShowVersionsPanel(false); 
                        }}
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