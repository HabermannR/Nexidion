import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, ButtonGroup, Dropdown, Form, InputGroup } from 'react-bootstrap';
import IconSelectorDropdown from './IconSelectorDropdown.jsx';
import apiClient from '../../api/apiClient.js'; // API Client importieren
import './ContentHeader.css';

export default function ContentHeader({
                                          currentVersion,
                                          vaultId,
                                          isEditing,
                                          onEditClick,
                                          onDeleteClick,
                                          showSummary,
                                          onToggleSummary
                                      }) {
    // NEU: QueryClient für die Invalidierung holen
    const queryClient = useQueryClient();

    // NEU: UI-Zustand für den Umbenennungs-Modus
    const [isRenaming, setIsRenaming] = useState(false);
    const [newTitle, setNewTitle] = useState('');

    // Stellt sicher, dass der Titel im Input-Feld aktuell ist, wenn sich der Node ändert
    useEffect(() => {
        if (currentVersion) {
            setNewTitle(currentVersion.title);
        }
    }, [currentVersion]);

    // NEU: useMutation für das Umbenennen des Nodes
    const renameNodeMutation = useMutation({
        mutationFn: (updatedNodeData) => {
            return apiClient.put(`/api/vaults/${vaultId}/nodes/${updatedNodeData.nodeId}`, {
                title: updatedNodeData.title,
                content: updatedNodeData.content,
            });
        },
        onSuccess: (data, variables) => { // Wir können die nodeId aus den `variables` bekommen
            console.log(`[MUTATION SUCCESS] Invalidating queries after rename.`);

            // Invalidiere den Baum, damit der neue Titel dort erscheint.
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });

            // === VERBESSERUNG ===
            // Invalidiere auch die Versionen, damit der Titel im Header und im Verlauf sofort aktuell ist.
            queryClient.invalidateQueries({ queryKey: ['versions', vaultId, variables.nodeId] });

            setIsRenaming(false);
        },
        onError: (error) => {
            console.error("Fehler beim Umbenennen des Nodes:", error);
            setIsRenaming(false);
        }
    });

    if (!currentVersion) {
        return <div className="content-header-container"><h1>Lädt...</h1></div>;
    }

    const handleRenameClick = () => {
        setIsRenaming(true);
        setNewTitle(currentVersion.title);
    };

    const handleRenameCancel = () => {
        setIsRenaming(false);
    };

    const handleRenameSubmit = (e) => {
        e.preventDefault();
        renameNodeMutation.mutate({
            nodeId: currentVersion.node_id,
            title: newTitle,
            content: currentVersion.content, // Den unveraenderten Inhalt aus der aktuellen Version nehmen
        });
    };

    return (
        <div className="content-header-container">
            <div className="me-2">
                <IconSelectorDropdown
                    currentVersion={currentVersion}
                    vaultId={vaultId}
                    nodeId={currentVersion.node_id}
                />
            </div>

            {isRenaming ? (
                <Form onSubmit={handleRenameSubmit} className="flex-grow-1">
                    <InputGroup>
                        <Form.Control
                            type="text"
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                            autoFocus
                            onKeyDown={(e) => { if (e.key === 'Escape') handleRenameCancel(); }}
                        />
                        <Button type="submit" variant="success" disabled={renameNodeMutation.isPending}>
                            {renameNodeMutation.isPending ? 'Speichern...' : <i className="bx bx-check"></i>}
                        </Button>
                        <Button variant="secondary" onClick={handleRenameCancel} disabled={renameNodeMutation.isPending}>
                            <i className="bx bx-x"></i>
                        </Button>
                    </InputGroup>
                </Form>
            ) : (
                <h1 className="content-title text-truncate text-center mx-2">{currentVersion.title}</h1>
            )}

            {!isEditing && !isRenaming && (
                <div className="action-buttons">
                    <ButtonGroup>
                        {/* 1. AI Summary Button (falls vorhanden) */}
                        {currentVersion?.ai_summary && (
                            <Button
                                variant={showSummary ? "info" : "outline-info"}
                                size="sm"
                                onClick={onToggleSummary}
                                title="AI Summary umschalten"
                            >
                                <i className="bx bx-bot"></i>
                                <span className="d-none d-md-inline ms-1">Summary</span>
                            </Button>
                        )}

                        {/* 2. Der Bearbeiten Button (der fehlte!) */}
                        <Button variant="primary" size="sm" onClick={onEditClick} title="Inhalt bearbeiten" className="edit-button-responsive">
                            <i className="bx bx-pencil"></i>
                            <span className="d-none d-sm-inline ms-1">Bearbeiten</span>
                        </Button>

                        {/* 3. Das Dropdown (hängt sich als "Split" optisch an den Bearbeiten-Button) */}
                        <Dropdown as={ButtonGroup}>
                            <Dropdown.Toggle split variant="primary" size="sm" id="node-actions-dropdown" title="Weitere Aktionen" />
                            <Dropdown.Menu align="end">
                                <Dropdown.Item onClick={handleRenameClick}>
                                    <i className="bx bx-rename me-2"></i> Umbenennen...
                                </Dropdown.Item>
                                <Dropdown.Divider />
                                <Dropdown.Item onClick={onDeleteClick} className="text-danger">
                                    <i className="bx bxs-trash me-2"></i> Löschen...
                                </Dropdown.Item>
                            </Dropdown.Menu>
                        </Dropdown>
                    </ButtonGroup>
                </div>
            )}
        </div>
    );
}