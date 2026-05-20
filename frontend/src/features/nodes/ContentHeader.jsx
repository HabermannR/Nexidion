// src/features/nodes/ContentHeader.jsx

import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, ButtonGroup, Dropdown, Form, InputGroup } from 'react-bootstrap';
import IconSelectorDropdown from './IconSelectorDropdown.jsx';
import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useToast } from '../../components/ToastProvider.jsx';
import './ContentHeader.css';

export default function ContentHeader({
                                          currentVersion,
                                          nodeId,
                                          vaultId,
                                          isEditing,
                                          onEditClick,
                                          onDeleteClick,
                                          showSummary,
                                          onToggleSummary,
                                          onAddSummary
                                      }) {
    const queryClient = useQueryClient();
    const openPrintPreview = useWorkspaceStore(state => state.openPrintPreview);
    const toast = useToast();

    const [isRenaming, setIsRenaming] = useState(false);
    const [newTitle, setNewTitle] = useState('');

    useEffect(() => {
        if (currentVersion) {
            setNewTitle(currentVersion.title);
        }
    }, [currentVersion]);

    const renameNodeMutation = useMutation({
        mutationFn: (updatedNodeData) => {
            return apiClient.put(`/api/vaults/${vaultId}/nodes/${updatedNodeData.nodeId}`, {
                title: updatedNodeData.title,
                content: updatedNodeData.content,
            });
        },
        onSuccess: (data, variables) => {
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            queryClient.invalidateQueries({ queryKey: ['versions', vaultId, variables.nodeId] });
            queryClient.invalidateQueries({ queryKey: ['nodeContent', vaultId, variables.nodeId] });
            setIsRenaming(false);
        },
        onError: (error) => {
            const msg = error.response?.data?.error || error.message || 'Rename failed.';
            toast.error(`Could not rename node: ${msg}`);
            setIsRenaming(false);
        }
    });

    if (!currentVersion) {
        return <div className="content-header-container"><h1>Loading...</h1></div>;
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
            nodeId: nodeId,
            title: newTitle,
            content: currentVersion.content,
        });
    };

    return (
        <div className="content-header-container">
            <div className="me-2">
                <IconSelectorDropdown
                    currentVersion={currentVersion}
                    vaultId={vaultId}
                    nodeId={nodeId}
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
                            {renameNodeMutation.isPending ? 'Saving...' : <i className="bx bx-check"></i>}
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
                        {/* Summary Button / Add Summary Button */}
                        {currentVersion?.ai_summary ? (
                            <Button
                                variant={showSummary ? "info" : "outline-info"}
                                size="sm"
                                onClick={onToggleSummary}
                                title="Toggle AI Summary"
                            >
                                <i className="bx bx-bot"></i>
                                <span className="d-none d-md-inline ms-1">Summary</span>
                            </Button>
                        ) : (
                            <Button
                                variant="outline-info"
                                size="sm"
                                onClick={onAddSummary}
                                title="Add AI Summary"
                            >
                                <i className="bx bx-bot"></i>
                                <span className="d-none d-md-inline ms-1">Add Summary</span>
                            </Button>
                        )}

                        {/* Edit Content Button */}
                        <Button variant="primary" size="sm" onClick={onEditClick} title="Edit Content" className="edit-button-responsive">
                            <i className="bx bx-pencil"></i>
                            <span className="d-none d-sm-inline ms-1">Edit</span>
                        </Button>

                        {/* Dropdown Menu */}
                        <Dropdown as={ButtonGroup}>
                            <Dropdown.Toggle split variant="primary" size="sm" id="node-actions-dropdown" title="More Actions" />
                            <Dropdown.Menu align="end">
                                <Dropdown.Item onClick={handleRenameClick}>
                                    <i className="bx bx-rename me-2"></i> Rename...
                                </Dropdown.Item>

                                {/* PRINT BUTTON */}
                                <Dropdown.Item onClick={() => openPrintPreview([currentVersion], null)}>
                                    <i className="bx bx-printer me-2"></i> Print...
                                </Dropdown.Item>

                                <Dropdown.Divider />
                                <Dropdown.Item onClick={onDeleteClick} className="text-danger">
                                    <i className="bx bxs-trash me-2"></i> Delete...
                                </Dropdown.Item>
                            </Dropdown.Menu>
                        </Dropdown>
                    </ButtonGroup>
                </div>
            )}
        </div>
    );
}