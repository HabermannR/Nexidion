// src/features/admin/VaultAccessManager.jsx
import React, { useState } from 'react';
import {
    Row, Col, Card, ListGroup, Table, Badge, Button,
    Spinner, Alert, Form
} from 'react-bootstrap';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function UserTypeBadge({ userType }) {
    return userType === 'llm_assistant'
        ? <Badge bg="info" className="ms-1">LLM</Badge>
        : <Badge bg="secondary" className="ms-1">Human</Badge>;
}

// ---------------------------------------------------------------------------
// Left panel — vault list
// ---------------------------------------------------------------------------

function VaultList({ selectedVaultId, onSelect }) {
    const { data: vaults, isLoading, isError } = useQuery({
        queryKey: ['admin', 'vaults'],
        queryFn: () => apiClient.get('/api/admin/vaults').then(r => r.data),
    });

    if (isLoading) return <div className="p-3 text-center"><Spinner size="sm" /> Loading…</div>;
    if (isError) return <Alert variant="danger" className="m-2">Failed to load vaults.</Alert>;

    return (
        <ListGroup variant="flush">
            {vaults?.map(v => (
                <ListGroup.Item
                    key={v.id}
                    action
                    active={v.id === selectedVaultId}
                    onClick={() => onSelect(v.id)}
                    className="d-flex justify-content-between align-items-start"
                >
                    <div>
                        <div className="fw-semibold">{v.name}</div>
                        <small className="text-muted">Owner: {v.owner_display_name}</small>
                    </div>
                    <Badge bg="secondary" pill>{v.access_count}</Badge>
                </ListGroup.Item>
            ))}
        </ListGroup>
    );
}

// ---------------------------------------------------------------------------
// Right panel — access detail for selected vault
// ---------------------------------------------------------------------------

function VaultAccessPanel({ vaultId }) {
    const queryClient = useQueryClient();
    const [selectedUserId, setSelectedUserId] = useState('');
    const [panelAlert, setPanelAlert] = useState(null);

    const { data, isLoading, isError } = useQuery({
        queryKey: ['admin', 'vault-access', vaultId],
        queryFn: () => apiClient.get(`/api/admin/vaults/${vaultId}/access`).then(r => r.data),
        enabled: !!vaultId,
    });

    const invalidate = () => {
        queryClient.invalidateQueries({ queryKey: ['admin', 'vault-access', vaultId] });
        queryClient.invalidateQueries({ queryKey: ['admin', 'vaults'] });
    };

    const grantMutation = useMutation({
        mutationFn: (userId) =>
            apiClient.post(`/api/admin/vaults/${vaultId}/access`, { user_id: userId }),
        onSuccess: () => { setPanelAlert(null); setSelectedUserId(''); invalidate(); },
        onError: (e) => setPanelAlert({ type: 'danger', message: e.response?.data?.error || 'Failed to grant access.' }),
    });

    const revokeMutation = useMutation({
        mutationFn: (userId) =>
            apiClient.delete(`/api/admin/vaults/${vaultId}/access/${userId}`),
        onSuccess: () => { setPanelAlert(null); invalidate(); },
        onError: (e) => setPanelAlert({ type: 'danger', message: e.response?.data?.error || 'Failed to revoke access.' }),
    });

    if (!vaultId) {
        return (
            <div className="d-flex align-items-center justify-content-center h-100 text-muted" style={{ minHeight: 200 }}>
                ← Select a vault to manage access
            </div>
        );
    }

    if (isLoading) return <div className="p-4 text-center"><Spinner /></div>;
    if (isError) return <Alert variant="danger" className="m-3">Failed to load access data.</Alert>;

    const { vault, access_list, available_users } = data;

    return (
        <div>
            <Card.Header>
                <strong>{vault.name}</strong>
                <span className="text-muted ms-2">— owned by {vault.owner_display_name} ({vault.owner_username})</span>
            </Card.Header>
            <Card.Body>
                {panelAlert && (
                    <Alert variant={panelAlert.type} dismissible onClose={() => setPanelAlert(null)}>
                        {panelAlert.message}
                    </Alert>
                )}

                {/* Current access list */}
                <h6 className="mb-2">Current access</h6>
                <Table size="sm" bordered className="mb-4">
                    <thead className="table-light">
                        <tr>
                            <th>User</th>
                            <th>Username</th>
                            <th>Type</th>
                            <th>Role</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {/* Owner row — always first, cannot be removed */}
                        <tr className="table-secondary">
                            <td>{vault.owner_display_name}</td>
                            <td>{vault.owner_username}</td>
                            <td><Badge bg="warning" text="dark">Owner</Badge></td>
                            <td>owner</td>
                            <td></td>
                        </tr>
                        {access_list.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="text-muted text-center">No additional users have access.</td>
                            </tr>
                        ) : (
                            access_list.map(u => (
                                <tr key={u.user_id}>
                                    <td>{u.display_name}</td>
                                    <td>{u.username}</td>
                                    <td><UserTypeBadge userType={u.user_type} /></td>
                                    <td>{u.role}</td>
                                    <td>
                                        <Button
                                            variant="outline-danger"
                                            size="sm"
                                            disabled={revokeMutation.isPending}
                                            onClick={() => revokeMutation.mutate(u.user_id)}
                                        >
                                            Revoke
                                        </Button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </Table>

                {/* Add access */}
                <h6 className="mb-2">Grant access</h6>
                {available_users.length === 0 ? (
                    <p className="text-muted">All users already have access.</p>
                ) : (
                    <div className="d-flex gap-2 align-items-center">
                        <Form.Select
                            size="sm"
                            style={{ maxWidth: 320 }}
                            value={selectedUserId}
                            onChange={e => setSelectedUserId(e.target.value)}
                        >
                            <option value="">— Select a user —</option>
                            {available_users.map(u => (
                                <option key={u.user_id} value={u.user_id}>
                                    {u.display_name} ({u.username}){u.user_type === 'llm_assistant' ? ' [LLM]' : ''}
                                </option>
                            ))}
                        </Form.Select>
                        <Button
                            variant="primary"
                            size="sm"
                            disabled={!selectedUserId || grantMutation.isPending}
                            onClick={() => grantMutation.mutate(parseInt(selectedUserId, 10))}
                        >
                            {grantMutation.isPending ? <Spinner size="sm" /> : 'Add'}
                        </Button>
                    </div>
                )}
            </Card.Body>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export default function VaultAccessManager() {
    const [selectedVaultId, setSelectedVaultId] = useState(null);

    return (
        <Row className="g-3 mt-1">
            <Col lg={4}>
                <Card className="h-100">
                    <Card.Header as="h6" className="mb-0">All Vaults</Card.Header>
                    <div style={{ overflowY: 'auto', maxHeight: 500 }}>
                        <VaultList
                            selectedVaultId={selectedVaultId}
                            onSelect={setSelectedVaultId}
                        />
                    </div>
                </Card>
            </Col>
            <Col lg={8}>
                <Card className="h-100">
                    <VaultAccessPanel vaultId={selectedVaultId} />
                </Card>
            </Col>
        </Row>
    );
}
