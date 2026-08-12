import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Container, Card, Button, Table, Alert, Spinner, Modal,
    Form as BootstrapForm, Row, Col, InputGroup, Badge, Nav
} from 'react-bootstrap';
import { useWorkspaceStore } from '../workspace/workspaceStore';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';
import { useToast } from '../../components/ToastProvider';

// ── Small helpers ────────────────────────────────────────────────────────────

function PasswordInput({ name, label, required = true }) {
    const [showPassword, setShowPassword] = useState(false);
    return (
        <BootstrapForm.Group className="mb-3" controlId={name}>
            <BootstrapForm.Label>{label}</BootstrapForm.Label>
            <InputGroup>
                <BootstrapForm.Control type={showPassword ? 'text' : 'password'} name={name} required={required} />
                <Button variant="outline-secondary" onClick={() => setShowPassword(p => !p)}>
                    {showPassword ? 'Hide' : 'Show'}
                </Button>
            </InputGroup>
        </BootstrapForm.Group>
    );
}

function InlineRename({ value, onSave, disabled }) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(value);
    const inputRef = useRef();

    const start = () => { setDraft(value); setEditing(true); setTimeout(() => inputRef.current?.select(), 0); };
    const cancel = () => setEditing(false);
    const commit = () => {
        const trimmed = draft.trim();
        if (trimmed && trimmed !== value) onSave(trimmed);
        setEditing(false);
    };
    const onKey = (e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') cancel(); };

    if (!editing) {
        return (
            <span
                role="button"
                title="Click to rename"
                onClick={disabled ? undefined : start}
                style={{ cursor: disabled ? 'default' : 'pointer', textDecoration: disabled ? 'none' : 'underline dotted' }}
            >
                {value}
            </span>
        );
    }
    return (
        <InputGroup size="sm" style={{ minWidth: 180 }}>
            <BootstrapForm.Control
                ref={inputRef}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onBlur={commit}
                onKeyDown={onKey}
                style={{ maxWidth: 220 }}
            />
            <Button variant="outline-success" onMouseDown={e => { e.preventDefault(); commit(); }}>✓</Button>
            <Button variant="outline-secondary" onMouseDown={e => { e.preventDefault(); cancel(); }}>✕</Button>
        </InputGroup>
    );
}

// ── Query key constants ──────────────────────────────────────────────────────

const QK_USERS      = ['admin', 'users'];
const QK_ALL_VAULTS = ['admin', 'allVaults'];

// ── Users section ─────────────────────────────────────────────────────────────

function UsersSection() {
    const toast = useToast();
    const queryClient = useQueryClient();
    const createUserFormRef = useRef();
    const passwordFormRef = useRef();
    const [modal, setModal] = useState({ type: null, user: null });

    const closeModal = () => setModal({ type: null, user: null });

    const { data: users, isLoading, isError, error } = useQuery({
        queryKey: QK_USERS,
        queryFn: () => apiClient.get('/api/admin/users').then(r => r.data),
    });

    const invalidate = () => queryClient.invalidateQueries({ queryKey: QK_USERS });

    const createMutation = useMutation({
        mutationFn: (payload) => apiClient.post('/api/admin/users', payload),
        onSuccess: (res) => { toast.success(`User "${res.data.username}" created.`); invalidate(); createUserFormRef.current?.reset(); },
        onError: (err) => toast.error(err.response?.data?.error || 'Error creating user.'),
    });

    const renameMutation = useMutation({
        mutationFn: ({ userId, display_name }) => apiClient.put(`/api/admin/users/${userId}`, { display_name }),
        onSuccess: () => { toast.success('Display name updated.'); invalidate(); },
        onError: (err) => toast.error(err.response?.data?.error || 'Error renaming user.'),
    });

    const deleteMutation = useMutation({
        mutationFn: (userId) => apiClient.delete(`/api/admin/users/${userId}`),
        onSuccess: () => { toast.success('User deleted.'); invalidate(); closeModal(); },
        onError: (err) => { toast.error(err.response?.data?.error || 'Error deleting user.'); closeModal(); },
    });

    const passwordMutation = useMutation({
        mutationFn: ({ userId, new_password }) => apiClient.put(`/api/admin/users/${userId}/password`, { new_password }),
        onSuccess: () => { toast.success('Password reset.'); passwordFormRef.current?.reset(); closeModal(); },
        onError: (err) => toast.error(err.response?.data?.error || 'Error resetting password.'),
    });

    const handleCreate = (e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        createMutation.mutate({
            username: f.get('username'),
            display_name: f.get('display_name'),
            password: f.get('password'),
            is_admin: f.get('is_admin') === 'on',
        });
    };

    const handlePasswordSubmit = (e) => {
        e.preventDefault();
        const pw = new FormData(e.currentTarget).get('new_password');
        if (!pw || pw.length < 8) { toast.error('Password must be at least 8 characters.'); return; }
        passwordMutation.mutate({ userId: modal.user.id, new_password: pw });
    };

    return (
        <>
            <Row className="g-4">
                <Col lg={4}>
                    <Card>
                        <Card.Header as="h5">Create New User</Card.Header>
                        <Card.Body>
                            <BootstrapForm ref={createUserFormRef} onSubmit={handleCreate}>
                                <BootstrapForm.Group className="mb-3">
                                    <BootstrapForm.Label>Username</BootstrapForm.Label>
                                    <BootstrapForm.Control type="text" name="username" required />
                                </BootstrapForm.Group>
                                <BootstrapForm.Group className="mb-3">
                                    <BootstrapForm.Label>Display Name</BootstrapForm.Label>
                                    <BootstrapForm.Control type="text" name="display_name" required />
                                </BootstrapForm.Group>
                                <PasswordInput name="password" label="Initial Password" />
                                <BootstrapForm.Check type="switch" id="is_admin_switch" name="is_admin" label="Make administrator" className="mb-3" />
                                <div className="d-grid">
                                    <Button type="submit" disabled={createMutation.isPending}>
                                        {createMutation.isPending ? <><Spinner size="sm" /> Creating…</> : 'Create User'}
                                    </Button>
                                </div>
                            </BootstrapForm>
                        </Card.Body>
                    </Card>
                </Col>

                <Col lg={8}>
                    <Card>
                        <Card.Header as="h5" className="d-flex align-items-center gap-2">
                            All Users {users ? <Badge bg="secondary" className="ms-1">{users.length}</Badge> : null}
                        </Card.Header>
                        <Card.Body className="p-0">
                            {isLoading && <div className="text-center p-4"><Spinner animation="border" size="sm" /> Loading…</div>}
                            {isError && <Alert variant="danger" className="m-3">Error: {error.response?.data?.error || error.message}</Alert>}
                            {users && (
                                <Table responsive hover className="mb-0 align-middle">
                                    <thead>
                                        <tr>
                                            <th>Username</th>
                                            <th>Display Name</th>
                                            <th>Role</th>
                                            <th className="text-end">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.map(u => (
                                            <tr key={u.id}>
                                                <td><code className="text-body">{u.username}</code></td>
                                                <td>
                                                    <InlineRename
                                                        value={u.display_name}
                                                        onSave={(name) => renameMutation.mutate({ userId: u.id, display_name: name })}
                                                        disabled={renameMutation.isPending}
                                                    />
                                                </td>
                                                <td>
                                                    {u.is_admin
                                                        ? <Badge bg="primary">Admin</Badge>
                                                        : <Badge bg="secondary">User</Badge>}
                                                </td>
                                                <td className="text-end">
                                                    <Button
                                                        variant="outline-secondary" size="sm" className="me-2"
                                                        onClick={() => setModal({ type: 'password', user: u })}
                                                    >
                                                        Reset password
                                                    </Button>
                                                    <Button
                                                        variant="outline-danger" size="sm"
                                                        onClick={() => setModal({ type: 'deleteUser', user: u })}
                                                        disabled={deleteMutation.isPending && deleteMutation.variables === u.id}
                                                    >
                                                        Delete
                                                    </Button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </Table>
                            )}
                        </Card.Body>
                    </Card>
                </Col>
            </Row>

            <Modal show={modal.type === 'deleteUser'} onHide={closeModal} centered>
                <Modal.Header closeButton><Modal.Title>Delete User</Modal.Title></Modal.Header>
                <Modal.Body>
                    Permanently delete <strong>{modal.user?.username}</strong>? Their vaults will be transferred to the admin account. This cannot be undone.
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={closeModal}>Cancel</Button>
                    <Button variant="danger" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(modal.user.id)}>
                        {deleteMutation.isPending ? 'Deleting…' : 'Delete permanently'}
                    </Button>
                </Modal.Footer>
            </Modal>

            <Modal show={modal.type === 'password'} onHide={closeModal} centered>
                <BootstrapForm ref={passwordFormRef} onSubmit={handlePasswordSubmit}>
                    <Modal.Header closeButton><Modal.Title>Reset password — {modal.user?.username}</Modal.Title></Modal.Header>
                    <Modal.Body><PasswordInput name="new_password" label="New Password" /></Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={closeModal}>Cancel</Button>
                        <Button variant="primary" type="submit" disabled={passwordMutation.isPending}>
                            {passwordMutation.isPending ? 'Saving…' : 'Save Password'}
                        </Button>
                    </Modal.Footer>
                </BootstrapForm>
            </Modal>
        </>
    );
}

// ── Vault Access Panel (inline, admin version) ────────────────────────────────
// Mirrors the owner VaultAccessPanel style: shown inline per vault row.

function AdminVaultAccessPanel({ vaultId }) {
    const queryClient = useQueryClient();
    const toast = useToast();
    const [selectedUserId, setSelectedUserId] = useState('');

    const qk = ['admin', 'vault-access', vaultId];

    const { data, isLoading, isError } = useQuery({
        queryKey: qk,
        queryFn: () => apiClient.get(`/api/admin/vaults/${vaultId}/access`).then(r => r.data),
        enabled: !!vaultId,
    });

    const invalidate = () => {
        queryClient.invalidateQueries({ queryKey: qk });
        queryClient.invalidateQueries({ queryKey: QK_ALL_VAULTS });
    };

    const grantMutation = useMutation({
        mutationFn: (userId) => apiClient.post(`/api/admin/vaults/${vaultId}/access`, { user_id: userId }),
        onSuccess: () => { setSelectedUserId(''); invalidate(); },
        onError: (e) => toast.error(e.response?.data?.error || 'Failed to grant access.'),
    });

    const revokeMutation = useMutation({
        mutationFn: (userId) => apiClient.delete(`/api/admin/vaults/${vaultId}/access/${userId}`),
        onSuccess: () => invalidate(),
        onError: (e) => toast.error(e.response?.data?.error || 'Failed to revoke access.'),
    });

    if (isLoading) return <div className="text-center py-3"><Spinner size="sm" /> Loading access…</div>;
    if (isError) return <Alert variant="danger" className="mt-2">Failed to load access data.</Alert>;
    if (!data) return null;

    const { vault, access_list, available_users } = data;

    return (
        <div className="mt-2">
            <h6 className="mb-2 text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Current access
            </h6>
            <Table size="sm" bordered className="mb-3">
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
                    <tr className="table-secondary">
                        <td>{vault.owner_display_name}</td>
                        <td><code className="text-body">{vault.owner_username}</code></td>
                        <td><Badge bg="warning" text="dark">Owner</Badge></td>
                        <td>owner</td>
                        <td></td>
                    </tr>
                    {access_list.length === 0 ? (
                        <tr>
                            <td colSpan={5} className="text-muted text-center py-2" style={{ fontSize: '0.85rem' }}>
                                No additional users have access.
                            </td>
                        </tr>
                    ) : (
                        access_list.map(u => (
                            <tr key={u.user_id}>
                                <td>{u.display_name}</td>
                                <td><code className="text-body">{u.username}</code></td>
                                <td>
                                    {u.user_type === 'llm_assistant'
                                        ? <Badge bg="info">LLM</Badge>
                                        : <Badge bg="secondary">Human</Badge>}
                                </td>
                                <td>{u.role}</td>
                                <td>
                                    <Button
                                        variant="outline-danger" size="sm"
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

            <h6 className="mb-2 text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Grant access
            </h6>
            {available_users.length === 0 ? (
                <p className="text-muted" style={{ fontSize: '0.85rem' }}>All users already have access.</p>
            ) : (
                <div className="d-flex gap-2 align-items-center">
                    <BootstrapForm.Select
                        size="sm"
                        style={{ maxWidth: 320 }}
                        value={selectedUserId}
                        onChange={e => setSelectedUserId(e.target.value)}
                    >
                        <option value="">— Select a user or LLM agent —</option>
                        {available_users.map(u => (
                            <option key={u.user_id} value={u.user_id}>
                                {u.display_name} ({u.username}){u.user_type === 'llm_assistant' ? ' [LLM]' : ''}
                            </option>
                        ))}
                    </BootstrapForm.Select>
                    <Button
                        variant="primary" size="sm"
                        disabled={!selectedUserId || grantMutation.isPending}
                        onClick={() => grantMutation.mutate(parseInt(selectedUserId, 10))}
                    >
                        {grantMutation.isPending ? <Spinner size="sm" /> : 'Add'}
                    </Button>
                </div>
            )}
        </div>
    );
}

// ── Vault row with inline access expand ──────────────────────────────────────

function VaultRow({ vault, renameMutation, deleteMutation }) {
    const [showAccess, setShowAccess] = useState(false);
    const isDeleting = deleteMutation.isPending && deleteMutation.variables === vault.id;

    return (
        <>
            <tr>
                <td className="text-muted" style={{ width: 50 }}>{vault.id}</td>
                <td>
                    <InlineRename
                        value={vault.name}
                        onSave={(name) => renameMutation.mutate({ vaultId: vault.id, name })}
                        disabled={renameMutation.isPending}
                    />
                </td>
                <td>
                    {vault.owner_display_name}{' '}
                    <span className="text-muted" style={{ fontSize: '0.85rem' }}>({vault.owner_username})</span>
                </td>
                <td>
                    <Badge bg="secondary">Normal</Badge>
                </td>
                <td>{vault.access_count}</td>
                <td className="text-muted" style={{ fontSize: '0.85rem' }}>
                    {new Date(vault.created_at).toLocaleDateString()}
                </td>
                <td className="text-end">
                    <div className="btn-group" role="group">
                        <Button
                            variant={showAccess ? 'info' : 'outline-info'}
                            size="sm"
                            onClick={() => setShowAccess(v => !v)}
                            disabled={isDeleting}
                        >
                            {showAccess ? 'Hide Access' : 'Access'}
                        </Button>
                        <Button
                            variant="outline-danger" size="sm"
                            onClick={() => {
                                // handled by parent via setConfirmDelete
                                deleteMutation._triggerConfirm(vault);
                            }}
                            disabled={isDeleting}
                        >
                            {isDeleting ? <Spinner size="sm" /> : 'Delete'}
                        </Button>
                    </div>
                </td>
            </tr>
            {showAccess && (
                <tr>
                    <td colSpan={7} style={{ background: '#f8f9fa', padding: '12px 20px' }}>
                        <AdminVaultAccessPanel vaultId={vault.id} />
                    </td>
                </tr>
            )}
        </>
    );
}

// ── Vaults section ────────────────────────────────────────────────────────────

function VaultsSection() {
    const toast = useToast();
    const queryClient = useQueryClient();
    const [confirmDelete, setConfirmDelete] = useState(null);

    const { data: vaults, isLoading, isError, error } = useQuery({
        queryKey: QK_ALL_VAULTS,
        queryFn: () => apiClient.get('/api/admin/vaults').then(r => r.data),
    });

    const invalidate = () => queryClient.invalidateQueries({ queryKey: QK_ALL_VAULTS });

    const renameMutation = useMutation({
        mutationFn: ({ vaultId, name }) => apiClient.put(`/api/admin/vaults/${vaultId}`, { name }),
        onSuccess: () => { toast.success('Vault renamed.'); invalidate(); },
        onError: (err) => toast.error(err.response?.data?.error || 'Error renaming vault.'),
    });

    const deleteMutation = useMutation({
        mutationFn: (vaultId) => apiClient.delete(`/api/admin/vaults/${vaultId}`),
        onSuccess: () => { toast.success('Vault deleted.'); invalidate(); setConfirmDelete(null); },
        onError: (err) => { toast.error(err.response?.data?.error || 'Error deleting vault.'); setConfirmDelete(null); },
    });

    // Attach a helper so VaultRow can trigger the confirm modal
    deleteMutation._triggerConfirm = setConfirmDelete;

    return (
        <>
            <Card>
                <Card.Header as="h5" className="d-flex align-items-center gap-2">
                    All Vaults
                    {vaults ? <Badge bg="secondary">{vaults.length}</Badge> : null}
                    <span className="ms-auto text-muted fw-normal" style={{ fontSize: '0.8rem' }}>
                        Click a vault name to rename · click Access to manage users
                    </span>
                </Card.Header>
                <Card.Body className="p-0">
                    {isLoading && <div className="text-center p-4"><Spinner animation="border" size="sm" /> Loading…</div>}
                    {isError && <Alert variant="danger" className="m-3">Error: {error.response?.data?.error || error.message}</Alert>}
                    {vaults && (
                        <Table responsive hover className="mb-0 align-middle">
                            <thead>
                                <tr>
                                    <th style={{ width: 50 }}>ID</th>
                                    <th>Name</th>
                                    <th>Owner</th>
                                    <th>Type</th>
                                    <th>Accesses</th>
                                    <th>Created</th>
                                    <th className="text-end">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {vaults.map(v => (
                                    <VaultRow
                                        key={v.id}
                                        vault={v}
                                        renameMutation={renameMutation}
                                        deleteMutation={deleteMutation}
                                    />
                                ))}
                            </tbody>
                        </Table>
                    )}
                </Card.Body>
            </Card>

            <Modal show={!!confirmDelete} onHide={() => setConfirmDelete(null)} centered>
                <Modal.Header closeButton><Modal.Title>Delete Vault</Modal.Title></Modal.Header>
                <Modal.Body>
                    Permanently delete vault <strong>"{confirmDelete?.name}"</strong> (owned by <strong>{confirmDelete?.owner_username}</strong>)?
                    All nodes and access rules inside it will be lost. This cannot be undone.
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setConfirmDelete(null)}>Cancel</Button>
                    <Button variant="danger" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(confirmDelete.id)}>
                        {deleteMutation.isPending ? 'Deleting…' : 'Delete permanently'}
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

const TABS = [
    { key: 'users',  label: 'Users' },
    { key: 'vaults', label: 'Vaults' },
];

export default function AdminDashboard() {
    const navigate = useNavigate();
    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);
    const lastActiveVaultId = useWorkspaceStore(state => state.lastActiveVaultId);
    const [activeTab, setActiveTab] = useState('users');

    const handleBackClick = () => {
        const lastPath = lastActiveVaultId ? lastValidPaths[lastActiveVaultId] : null;
        navigate(lastPath || (lastActiveVaultId ? `/vaults/${lastActiveVaultId}` : '/'));
    };

    return (
        <Container className="p-4" style={{ height: '100%', overflowY: 'auto' }}>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h1 className="mb-0">Admin Dashboard</h1>
                <Button onClick={handleBackClick} variant="secondary">Back to Workspace</Button>
            </div>

            <Nav variant="tabs" className="mb-4" activeKey={activeTab} onSelect={k => setActiveTab(k)}>
                {TABS.map(t => (
                    <Nav.Item key={t.key}>
                        <Nav.Link eventKey={t.key}>{t.label}</Nav.Link>
                    </Nav.Item>
                ))}
            </Nav>

            {activeTab === 'users' && <UsersSection />}

            {activeTab === 'vaults' && <VaultsSection />}

        </Container>
    );
}
