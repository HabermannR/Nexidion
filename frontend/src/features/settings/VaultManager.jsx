// src/features/vaults/VaultManager.jsx

import React, { useState, useEffect, useRef } from 'react';
// ADDED: useParams to read the vaultId from the URL if activeVault is not present
import { Link, useOutletContext, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
    Container,
    Row,
    Col,
    Card,
    Button,
    Form as BootstrapForm,
    Table,
    Alert,
    Spinner,
    InputGroup
} from 'react-bootstrap';
import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useToast } from '../../components/ToastProvider.jsx';

// --- VaultRow Component (Refactored - NO CHANGES) ---
function VaultRow({ vault, activeVault, vaultsCount, renameMutation, deleteMutation }) {
    const [isEditing, setIsEditing] = useState(false);

    // Check if a mutation targeting THIS row is in progress
    const isRenaming = renameMutation.isPending && renameMutation.variables?.vaultId === vault.id;
    const isDeleting = deleteMutation.isPending && deleteMutation.variables === vault.id;

    // Close editing mode on successful rename
    useEffect(() => {
        if (renameMutation.isSuccess) {
            setIsEditing(false);
        }
    }, [renameMutation.isSuccess]);

    const handleRenameSubmit = (e) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const newName = formData.get('newName');
        if (newName && newName.trim() !== '') {
            renameMutation.mutate({ vaultId: vault.id, newName: newName.trim() });
        }
    };

    const handleDelete = () => {
        if (window.confirm(`Are you sure you want to delete the vault "${vault.name}"?`)) {
            deleteMutation.mutate(vault.id);
        }
    };

    return (
        <tr key={vault.id}>
            <td>
                {isEditing ? (
                    <BootstrapForm onSubmit={handleRenameSubmit} className="d-flex">
                        <InputGroup>
                            <BootstrapForm.Control
                                type="text"
                                name="newName"
                                defaultValue={vault.name}
                                autoFocus
                                disabled={isRenaming}
                            />
                            <Button type="submit" variant="outline-success" size="sm" disabled={isRenaming}>
                                {isRenaming ? <Spinner size="sm" /> : '✓'}
                            </Button>
                            <Button variant="outline-secondary" size="sm" onClick={() => setIsEditing(false)} disabled={isRenaming}>
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
                    <Link to={`/vaults/${vault.id}`} className="btn btn-sm btn-outline-primary">
                        Activate
                    </Link>
                )}
            </td>
            <td>
                {!isEditing && (
                    <div className="btn-group" role="group">
                        <Button variant="outline-primary" size="sm" onClick={() => setIsEditing(true)} disabled={isDeleting || isRenaming}>
                            Rename
                        </Button>
                        <Button
                            variant="outline-danger"
                            size="sm"
                            onClick={handleDelete}
                            disabled={isDeleting || isRenaming || vaultsCount <= 1}
                            title={vaultsCount <= 1 ? "The last vault cannot be deleted" : ""}
                        >
                            {isDeleting ? <Spinner size="sm" /> : 'Delete'}
                        </Button>
                    </div>
                )}
            </td>
        </tr>
    );
}


// --- Main VaultManager Component (Refactored) ---
export default function VaultManager() {
    // FIX: useOutletContext is not robust enough, we use useParams as a fallback
    const { activeVault } = useOutletContext() || {};
    const { vaultId } = useParams(); // Get the vaultId from the URL
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    // FIX: We read the vault-specific path object
    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);

    // FIX: We determine the correct path for the current context
    const currentVaultId = activeVault?.id || vaultId;
    const lastValidPathForThisVault = lastValidPaths ? lastValidPaths[currentVaultId] : null;


    const [isBatchMode, setIsBatchMode] = useState(false);
    const [successMsg, setSuccessMsg] = useState(null);
    const formRef = useRef();
    const inputRef = useRef();
    const toast = useToast();

    // --- DATA FETCHING with useQuery ---
    const { data: vaults, isLoading, isError, error: loaderError } = useQuery({
        queryKey: ['vaults'],
        queryFn: () => apiClient.get('/api/vaults/').then(res => res.data)
    });

    // --- MUTATIONS ---
    const createVaultMutation = useMutation({
        mutationFn: (name) => apiClient.post('/api/vaults/', { name }),
        onSuccess: (response) => {
            const newVault = response.data;
            queryClient.invalidateQueries({ queryKey: ['vaults'] });
            queryClient.invalidateQueries({ queryKey: ['allVaults'] });
            setSuccessMsg(`Vault "${newVault.name}" was successfully created.`);
            if (isBatchMode) {
                formRef.current?.reset();
                inputRef.current?.focus();
            } else {
                navigate(`/vaults/${newVault.id}`);
            }
        },
        onError: (err) => {
            toast.error(err.response?.data?.error || 'Failed to create vault.');
        }
    });

    const renameVaultMutation = useMutation({
        mutationFn: ({ vaultId, newName }) => apiClient.put(`/api/vaults/${vaultId}`, { name: newName }),
        onSuccess: (response) => {
            const updatedVault = response.data;
            queryClient.invalidateQueries({ queryKey: ['vaults'] });
            queryClient.invalidateQueries({ queryKey: ['allVaults'] });
            setSuccessMsg(`Vault successfully renamed to "${updatedVault.name}".`);
        },
        onError: (err) => toast.error(err.response?.data?.error || 'Renaming failed.')
    });

    const deleteVaultMutation = useMutation({
        mutationFn: (vaultId) => apiClient.delete(`/api/vaults/${vaultId}`),
        onSuccess: (data, vaultIdToDelete) => {
            queryClient.invalidateQueries({ queryKey: ['vaults']}).then(() => {
                const remainingVaults = queryClient.getQueryData(['vaults']);
                if (activeVault?.id === vaultIdToDelete) {
                    if (remainingVaults && remainingVaults.length > 0) {
                        navigate(`/vaults/${remainingVaults[0].id}`);
                    } else {
                        navigate('/settings/vaults');
                    }
                }
            });
            queryClient.invalidateQueries({ queryKey: ['allVaults'] });
            setSuccessMsg('Vault was successfully deleted.');
        },
        onError: (err) => toast.error(err.response?.data?.error || 'Deletion failed.')
    });

    const handleCreateSubmit = (event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const name = formData.get('name');
        if (name && name.trim() !== '') {
            createVaultMutation.mutate(name.trim());
        }
    };

    const handleBackClick = () => {
        // FIX: We use the vault-specific path
        navigate(lastValidPathForThisVault || (currentVaultId ? `/vaults/${currentVaultId}` : '/'));
    };

    const isSubmitting = createVaultMutation.isPending || renameVaultMutation.isPending || deleteVaultMutation.isPending;

    return (
        <Container className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>Vault Management</h2>
                <Button onClick={handleBackClick} variant="secondary">
                    Back to Workspace
                </Button>
            </div>

            {successMsg && <Alert variant="success" onClose={() => setSuccessMsg(null)} dismissible>{successMsg}</Alert>}

            {/* The rest of the component remains unchanged... */}
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
                                    checked={isBatchMode} onChange={(e) => setIsBatchMode(e.target.checked)}
                                    disabled={createVaultMutation.isPending}
                                />
                            </Col>
                            <Col xs={5} md={4} className="d-flex align-items-end">
                                <Button type="submit" variant="primary" disabled={createVaultMutation.isPending} className="w-100">
                                    {createVaultMutation.isPending ? (
                                        <><Spinner as="span" animation="border" size="sm" /> Creating...</>
                                    ) : 'Create Vault'}
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
                            {vaults.map((vault) => (
                                <VaultRow
                                    key={vault.id} vault={vault}
                                    activeVault={activeVault} vaultsCount={vaults.length}
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