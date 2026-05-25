// src/features/settings/VaultManager.jsx

import React, { useState, useEffect, useRef } from 'react';
import { Link, useOutletContext, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
    Container, Row, Col, Card, Button,
    Form as BootstrapForm, Table, Alert, Spinner, InputGroup,
} from 'react-bootstrap';
import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useToast } from '../../components/ToastProvider.jsx';
import { useVaultsQuery } from '../vaults/hooks/useVaultsQuery.js';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery.js';

// ─── VaultRow ─────────────────────────────────────────────────────────────────

function VaultRow({ vault, activeVault, vaultsCount, renameMutation, deleteMutation }) {
    const [isEditing, setIsEditing] = useState(false);

    const isRenaming = renameMutation.isPending && renameMutation.variables?.vaultId === vault.id;
    const isDeleting = deleteMutation.isPending && deleteMutation.variables === vault.id;

    useEffect(() => {
        if (renameMutation.isSuccess) setIsEditing(false);
    }, [renameMutation.isSuccess]);

    const handleRenameSubmit = (e) => {
        e.preventDefault();
        const newName = new FormData(e.currentTarget).get('newName');
        if (newName?.trim()) {
            renameMutation.mutate({ vaultId: vault.id, newName: newName.trim() });
        }
    };

    const handleDelete = () => {
        if (window.confirm(`Are you sure you want to delete the vault "${vault.name}"?`)) {
            deleteMutation.mutate(vault.id);
        }
    };

    return (
        <tr>
            <td>
                {isEditing ? (
                    <BootstrapForm onSubmit={handleRenameSubmit} className="d-flex">
                        <InputGroup>
                            <BootstrapForm.Control
                                type="text" name="newName"
                                defaultValue={vault.name}
                                autoFocus disabled={isRenaming}
                            />
                            <Button type="submit" variant="outline-success" size="sm" disabled={isRenaming}>
                                {isRenaming ? <Spinner size="sm" /> : '✓'}
                            </Button>
                            <Button variant="outline-secondary" size="sm"
                                onClick={() => setIsEditing(false)} disabled={isRenaming}>
                                ✕
                            </Button>
                        </InputGroup>
                    </BootstrapForm>
                ) : (
                    <strong>{vault.name}</strong>
                )}
            </td>
            <td>
                {activeVault?.id === vault.id ? (
                    <span className="badge bg-success">Active</span>
                ) : (
                    // FIX: vault change now goes through Link which triggers router-level
                    // vaultId change → WorkspaceLayout's useEffect clears selectedNodeIds.
                    // The extra clearSelection() call below is a belt-and-suspenders guard
                    // for cases where the vault is already loaded but the store wasn't reset
                    // (e.g. same vaultId after a page reload).
                    <ActivateVaultLink vaultId={vault.id} />
                )}
            </td>
            <td>
                {!isEditing && (
                    <div className="btn-group" role="group">
                        <Button variant="outline-primary" size="sm"
                            onClick={() => setIsEditing(true)}
                            disabled={isDeleting || isRenaming}>
                            Rename
                        </Button>
                        <Button
                            variant="outline-danger" size="sm"
                            onClick={handleDelete}
                            disabled={isDeleting || isRenaming || vaultsCount <= 1}
                            title={vaultsCount <= 1 ? 'The last vault cannot be deleted' : ''}
                        >
                            {isDeleting ? <Spinner size="sm" /> : 'Delete'}
                        </Button>
                    </div>
                )}
            </td>
        </tr>
    );
}

// ─── ActivateVaultLink ────────────────────────────────────────────────────────
//
// Extracts the vault-activation click into its own component so we can call
// clearSelection() *before* navigation. Without this, the selected node IDs
// from the old vault bleed into the new vault's context until the workspace
// layout remounts — which can cause the agent tab to submit tasks with stale
// node IDs that don't exist in the new vault.

function ActivateVaultLink({ vaultId }) {
    const clearSelection = useWorkspaceStore(state => state.clearSelection);
    const navigate       = useNavigate();

    const handleActivate = (e) => {
        e.preventDefault();
        clearSelection();          // ← FIX: empty selected nodes before switching vault
        navigate(`/vaults/${vaultId}`);
    };

    return (
        <a href={`/vaults/${vaultId}`}
            className="btn btn-sm btn-outline-primary"
            onClick={handleActivate}>
            Activate
        </a>
    );
}

// ─── Main VaultManager ────────────────────────────────────────────────────────

export default function VaultManager() {
    const { activeVault }  = useOutletContext() || {};
    const { vaultId }      = useParams();
    const navigate         = useNavigate();
    const queryClient      = useQueryClient();
    const toast            = useToast();

    const lastValidPaths        = useWorkspaceStore(state => state.lastValidPaths);
    const currentVaultId        = activeVault?.id || vaultId;
    const lastValidPathForThisVault = lastValidPaths?.[currentVaultId] ?? null;

    const [isBatchMode, setIsBatchMode] = useState(false);
    const [successMsg,  setSuccessMsg]  = useState(null);
    const formRef  = useRef();
    const inputRef = useRef();

    const { data: vaults, isLoading, isError, error: loaderError } = useVaultsQuery();

    // --- Mutations ---

    const createVaultMutation = useMutation({
        mutationFn: (name) => apiClient.post('/api/vaults/', { name }),
        onSuccess: (response) => {
            const newVault = response.data;
            queryClient.invalidateQueries({ queryKey: ['allVaults'] });
            setSuccessMsg(`Vault "${newVault.name}" was successfully created.`);
            if (isBatchMode) {
                formRef.current?.reset();
                inputRef.current?.focus();
            } else {
                navigate(`/vaults/${newVault.id}`);
            }
        },
        onError: (err) => toast.error(err.response?.data?.error || 'Failed to create vault.'),
    });

    const renameVaultMutation = useMutation({
        mutationFn: ({ vaultId, newName }) =>
            apiClient.put(`/api/vaults/${vaultId}`, { name: newName }),
        onSuccess: (response) => {
            queryClient.invalidateQueries({ queryKey: ['allVaults'] });
            setSuccessMsg(`Vault successfully renamed to "${response.data.name}".`);
        },
        onError: (err) => toast.error(err.response?.data?.error || 'Renaming failed.'),
    });

    const deleteVaultMutation = useMutation({
        mutationFn: (vaultId) => apiClient.delete(`/api/vaults/${vaultId}`),
        onSuccess: async (_, vaultIdToDelete) => {
            setSuccessMsg('Vault was successfully deleted.');

            // Fetch the fresh vault list from the server — invalidateQueries only
            // marks the cache stale but does not await the refetch, so getQueryData
            // immediately after would still return the stale list including the
            // deleted vault. refetchQueries actually awaits the network round-trip.
            await queryClient.refetchQueries({ queryKey: ['allVaults'] });

            if (activeVault?.id !== vaultIdToDelete) {
                // User was not on the deleted vault — no redirect needed.
                return;
            }

            const remaining = queryClient.getQueryData(['allVaults']);
            if (!remaining?.length) {
                navigate('/settings/vaults');
                return;
            }

            // Navigate to the root node of the first remaining vault so the user
            // lands on a valid node rather than a bare /vaults/:id URL.
            const nextVaultId = remaining[0].id;
            try {
                const res = await apiClient.get(`/api/vaults/${nextVaultId}/nodes/`);
                const tree = res.data;
                const allFlat = [];
                const stack = Array.isArray(tree) ? [...tree] : [];
                while (stack.length) {
                    const node = stack.pop();
                    if (!node) continue;
                    const { children, ...rest } = node;
                    allFlat.push(rest);
                    if (Array.isArray(children)) stack.push(...children);
                }
                const rootNode = allFlat.find(n => n.parent_id === null);
                if (rootNode) {
                    navigate(`/vaults/${nextVaultId}/nodes/${rootNode.id}`);
                } else {
                    navigate(`/vaults/${nextVaultId}`);
                }
            } catch {
                navigate(`/vaults/${nextVaultId}`);
            }
        },
        onError: (err) => toast.error(err.response?.data?.error || 'Deletion failed.'),
    });

    const handleCreateSubmit = (event) => {
        event.preventDefault();
        const name = new FormData(event.currentTarget).get('name');
        if (name?.trim()) createVaultMutation.mutate(name.trim());
    };

    const handleBackClick = () => {
        navigate(lastValidPathForThisVault || (currentVaultId ? `/vaults/${currentVaultId}` : '/'));
    };

    const isSubmitting =
        createVaultMutation.isPending ||
        renameVaultMutation.isPending ||
        deleteVaultMutation.isPending;

    return (
        <Container className="py-4" style={{ height: '100%', overflowY: 'auto' }}>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>Vault Management</h2>
                <Button onClick={handleBackClick} variant="secondary">
                    Back to Workspace
                </Button>
            </div>

            {successMsg && (
                <Alert variant="success" onClose={() => setSuccessMsg(null)} dismissible>
                    {successMsg}
                </Alert>
            )}

            <Card className="mb-4">
                <Card.Header as="h5">Create New Vault</Card.Header>
                <Card.Body>
                    <BootstrapForm ref={formRef} onSubmit={handleCreateSubmit}>
                        <Row>
                            <Col md={12}>
                                <BootstrapForm.Group controlId="new-vault-name">
                                    <BootstrapForm.Label>Vault Name</BootstrapForm.Label>
                                    <BootstrapForm.Control
                                        type="text" name="name"
                                        placeholder="Enter name for the new vault..."
                                        required disabled={createVaultMutation.isPending}
                                        ref={inputRef} autoFocus
                                    />
                                </BootstrapForm.Group>
                            </Col>
                        </Row>
                        <Row className="mt-3">
                            <Col xs={7} md={8}>
                                <BootstrapForm.Check
                                    type="switch" id="batch-mode-switch"
                                    label="Batch creation (create & stay here)"
                                    checked={isBatchMode}
                                    onChange={e => setIsBatchMode(e.target.checked)}
                                    disabled={createVaultMutation.isPending}
                                />
                            </Col>
                            <Col xs={5} md={4} className="d-flex align-items-end">
                                <Button type="submit" variant="primary"
                                    disabled={createVaultMutation.isPending} className="w-100">
                                    {createVaultMutation.isPending
                                        ? <><Spinner as="span" animation="border" size="sm" /> Creating...</>
                                        : 'Create Vault'}
                                </Button>
                            </Col>
                        </Row>
                    </BootstrapForm>
                </Card.Body>
            </Card>

            <Card>
                <Card.Header as="h5">Existing Vaults</Card.Header>
                <Card.Body>
                    {isLoading ? (
                        <div className="text-center"><Spinner animation="border" /> Loading vaults...</div>
                    ) : isError ? (
                        <Alert variant="danger">{loaderError.message}</Alert>
                    ) : vaults.length === 0 ? (
                        <Alert variant="info">No vaults available. Create your first vault above.</Alert>
                    ) : (
                        <Table responsive hover>
                            <thead>
                                <tr><th>Name</th><th>Status</th><th>Actions</th></tr>
                            </thead>
                            <tbody>
                                {vaults.map(vault => (
                                    <VaultRow
                                        key={vault.id}
                                        vault={vault}
                                        activeVault={activeVault}
                                        vaultsCount={vaults.length}
                                        renameMutation={renameVaultMutation}
                                        deleteMutation={deleteVaultMutation}
                                        isSubmitting={isSubmitting}
                                    />
                                ))}
                            </tbody>
                        </Table>
                    )}
                </Card.Body>
            </Card>
        </Container>
    );
}
