// src/features/vaults/VaultManager.jsx

import React, { useState, useEffect, useRef } from 'react';
// HINZUGEFÜGT: useParams, um die vaultId aus der URL zu lesen, falls activeVault nicht da ist
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

// --- VaultRow Component (Refactored - KEINE ÄNDERUNGEN) ---
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
        if (window.confirm(`Möchten Sie den Vault "${vault.name}" wirklich löschen?`)) {
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
                    <span className="badge bg-success">Aktiv</span>
                ) : (
                    <Link to={`/vaults/${vault.id}`} className="btn btn-sm btn-outline-primary">
                        Aktivieren
                    </Link>
                )}
            </td>
            <td>
                {!isEditing && (
                    <div className="btn-group" role="group">
                        <Button variant="outline-primary" size="sm" onClick={() => setIsEditing(true)} disabled={isDeleting || isRenaming}>
                            Umbenennen
                        </Button>
                        <Button
                            variant="outline-danger"
                            size="sm"
                            onClick={handleDelete}
                            disabled={isDeleting || isRenaming || vaultsCount <= 1}
                            title={vaultsCount <= 1 ? "Der letzte Vault kann nicht gelöscht werden" : ""}
                        >
                            {isDeleting ? <Spinner size="sm" /> : 'Löschen'}
                        </Button>
                    </div>
                )}
            </td>
        </tr>
    );
}


// --- Main VaultManager Component (Refactored) ---
export default function VaultManager() {
    // KORREKTUR: useOutletContext ist nicht robust genug, wir nutzen useParams als Fallback
    const { activeVault } = useOutletContext() || {};
    const { vaultId } = useParams(); // Holen der vaultId aus der URL
    const navigate = useNavigate();
    const queryClient = useQueryClient();

    // KORREKTUR: Wir lesen das vault-spezifische Pfad-Objekt
    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);

    // KORREKTUR: Wir ermitteln den korrekten Pfad für den aktuellen Kontext
    const currentVaultId = activeVault?.id || vaultId;
    const lastValidPathForThisVault = lastValidPaths ? lastValidPaths[currentVaultId] : null;


    const [isBatchMode, setIsBatchMode] = useState(false);
    const [alert, setAlert] = useState(null); // Local alert state for success/error messages
    const formRef = useRef();
    const inputRef = useRef();

    // --- DATA FETCHING with useQuery (KEINE ÄNDERUNG) ---
    const { data: vaults, isLoading, isError, error: loaderError } = useQuery({
        queryKey: ['vaults'],
        queryFn: () => apiClient.get('/api/vaults/').then(res => res.data)
    });

    // --- MUTATIONS (KEINE ÄNDERUNGEN) ---
    const createVaultMutation = useMutation({
        mutationFn: (name) => apiClient.post('/api/vaults/', { name }),
        onSuccess: (response) => {
            const newVault = response.data;
            queryClient.invalidateQueries({ queryKey: ['vaults'] });
            queryClient.invalidateQueries({ queryKey: ['allVaults'] });
            setAlert({ type: 'success', message: `Vault "${newVault.name}" wurde erfolgreich erstellt.` });
            if (isBatchMode) {
                formRef.current?.reset();
                inputRef.current?.focus();
            } else {
                navigate(`/vaults/${newVault.id}`);
            }
        },
        onError: (err) => {
            setAlert({ type: 'danger', message: err.response?.data?.error || 'Ein Fehler ist aufgetreten.' });
        }
    });

    const renameVaultMutation = useMutation({
        mutationFn: ({ vaultId, newName }) => apiClient.put(`/api/vaults/${vaultId}`, { name: newName }),
        onSuccess: (response) => {
            const updatedVault = response.data;
            queryClient.invalidateQueries({ queryKey: ['vaults'] });
            queryClient.invalidateQueries({ queryKey: ['allVaults'] });
            setAlert({ type: 'success', message: `Vault erfolgreich in "${updatedVault.name}" umbenannt.` });
        },
        onError: (err) => setAlert({ type: 'danger', message: err.response?.data?.error || 'Umbenennen fehlgeschlagen.' })
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
            setAlert({ type: 'success', message: 'Vault wurde erfolgreich gelöscht.' });
        },
        onError: (err) => setAlert({ type: 'danger', message: err.response?.data?.error || 'Löschen fehlgeschlagen.' })
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
        // KORREKTUR: Wir nutzen den vault-spezifischen Pfad
        navigate(lastValidPathForThisVault || (currentVaultId ? `/vaults/${currentVaultId}` : '/'));
    };

    const isSubmitting = createVaultMutation.isPending || renameVaultMutation.isPending || deleteVaultMutation.isPending;

    return (
        <Container className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>Vault-Verwaltung</h2>
                <Button onClick={handleBackClick} variant="secondary">
                    Zurück zum Workspace
                </Button>
            </div>

            {alert && <Alert variant={alert.type} onClose={() => setAlert(null)} dismissible>{alert.message}</Alert>}

            {/* Der Rest der Komponente bleibt unverändert... */}
            <Card className="mb-4">
                <Card.Header as="h5">Neuen Vault erstellen</Card.Header>
                <Card.Body>
                    <BootstrapForm ref={formRef} onSubmit={handleCreateSubmit}>
                        <Row>
                            <Col md={12}>
                                <BootstrapForm.Group controlId="new-vault-name">
                                    <BootstrapForm.Label>Vault-Name</BootstrapForm.Label>
                                    <BootstrapForm.Control
                                        type="text" name="name"
                                        placeholder="Namen für den neuen Vault eingeben..."
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
                                    label="Batch-Erstellung (erstellen & hier bleiben)"
                                    checked={isBatchMode} onChange={(e) => setIsBatchMode(e.target.checked)}
                                    disabled={createVaultMutation.isPending}
                                />
                            </Col>
                            <Col xs={5} md={4} className="d-flex align-items-end">
                                <Button type="submit" variant="primary" disabled={createVaultMutation.isPending} className="w-100">
                                    {createVaultMutation.isPending ? (
                                        <><Spinner as="span" animation="border" size="sm" /> Erstellen...</>
                                    ) : 'Vault erstellen'}
                                </Button>
                            </Col>
                        </Row>
                    </BootstrapForm>
                </Card.Body>
            </Card>

            <Card>
                <Card.Header as="h5">Bestehende Vaults</Card.Header>
                <Card.Body>
                    {isLoading ? (
                        <div className="text-center"><Spinner animation="border" /> Lade Vaults...</div>
                    ) : isError ? (
                        <Alert variant="danger">{loaderError.message}</Alert>
                    ) : vaults.length === 0 ? (
                        <Alert variant="info">Keine Vaults vorhanden. Erstellen Sie Ihren ersten Vault oben.</Alert>
                    ) : (
                        <Table responsive hover>
                            <thead>
                            <tr><th>Name</th><th>Status</th><th>Aktionen</th></tr>
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