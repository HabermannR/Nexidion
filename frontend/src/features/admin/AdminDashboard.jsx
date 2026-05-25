import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Container, Card, Button, Table, Alert, Spinner, Modal,
    Form as BootstrapForm, Row, Col, InputGroup, Badge
} from 'react-bootstrap';
import { useWorkspaceStore } from '../workspace/workspaceStore';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';
import VaultAccessManager from './VaultAccessManager';
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

// Inline rename input that saves on Enter / blur
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

// ── Query key constants (single source of truth) ─────────────────────────────

const QK_USERS      = ['admin', 'users'];
const QK_ALL_VAULTS = ['admin', 'allVaults'];

// ── Users section ─────────────────────────────────────────────────────────────

function UsersSection() {
    const toast = useToast();
    const queryClient = useQueryClient();
    const createUserFormRef = useRef();
    const passwordFormRef = useRef();
    const [modal, setModal] = useState({ type: null, user: null }); // 'deleteUser' | 'password'

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
                {/* Create user */}
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

                {/* User list */}
                <Col lg={8}>
                    <Card>
                        <Card.Header as="h5">
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
                                                    {u.is_guest && <Badge bg="warning" text="dark" className="ms-1">Guest</Badge>}
                                                </td>
                                                <td className="text-end">
                                                    {/* Guests have no password — hide the reset button for them */}
                                                    {!u.is_guest && (
                                                        <Button
                                                            variant="outline-secondary" size="sm" className="me-2"
                                                            onClick={() => setModal({ type: 'password', user: u })}
                                                        >
                                                            Reset password
                                                        </Button>
                                                    )}
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

            {/* Delete user modal */}
            <Modal show={modal.type === 'deleteUser'} onHide={closeModal} centered>
                <Modal.Header closeButton><Modal.Title>Delete User</Modal.Title></Modal.Header>
                <Modal.Body>
                    {modal.user?.is_guest
                        ? <>Permanently delete guest <strong>{modal.user?.username}</strong>? Their demo vault will be wiped. This cannot be undone.</>
                        : <>Permanently delete <strong>{modal.user?.username}</strong>? Their vaults will be transferred to the admin account. This cannot be undone.</>
                    }
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={closeModal}>Cancel</Button>
                    <Button variant="danger" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(modal.user.id)}>
                        {deleteMutation.isPending ? 'Deleting…' : 'Delete permanently'}
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Password modal */}
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

// ── Vaults section ────────────────────────────────────────────────────────────

function VaultsSection() {
    const toast = useToast();
    const queryClient = useQueryClient();
    const [confirmDelete, setConfirmDelete] = useState(null); // vault object

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

    return (
        <>
            <Card>
                <Card.Header as="h5" className="d-flex align-items-center gap-2">
                    All Vaults
                    {vaults ? <Badge bg="secondary">{vaults.length}</Badge> : null}
                    <span className="ms-auto text-muted fw-normal" style={{ fontSize: '0.8rem' }}>
                        Click a vault name to rename it inline
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
                                    <tr key={v.id}>
                                        <td className="text-muted">{v.id}</td>
                                        <td>
                                            <InlineRename
                                                value={v.name}
                                                onSave={(name) => renameMutation.mutate({ vaultId: v.id, name })}
                                                disabled={renameMutation.isPending}
                                            />
                                        </td>
                                        <td>
                                            {v.owner_display_name}{' '}
                                            <span className="text-muted" style={{ fontSize: '0.85rem' }}>({v.owner_username})</span>
                                        </td>
                                        <td>
                                            {/* is_guest_vault is now a proper boolean from the API */}
                                            {v.is_guest_vault
                                                ? <Badge bg="warning" text="dark">Demo</Badge>
                                                : <Badge bg="secondary">Normal</Badge>}
                                        </td>
                                        <td>{v.access_count}</td>
                                        <td className="text-muted" style={{ fontSize: '0.85rem' }}>
                                            {new Date(v.created_at).toLocaleDateString()}
                                        </td>
                                        <td className="text-end">
                                            <Button
                                                variant="outline-danger" size="sm"
                                                onClick={() => setConfirmDelete(v)}
                                                disabled={deleteMutation.isPending && deleteMutation.variables === v.id}
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

            {/* Delete vault modal */}
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

// ── Developer Tools ─────────────────────────────────────────────────────────

function DemoScriptExtractor() {
    const toast = useToast();
    const [taskId, setTaskId] = useState('');
    const [script, setScript] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleExtract = async () => {
        if (!taskId.trim()) return;
        setIsLoading(true);
        try {
            const res = await apiClient.get(`/api/tasks/${taskId.trim()}`);
            const task = res.data;
            const ops = task.operations || [];

            const opsJson = JSON.stringify(ops, null, 4);
            const outputCode = `import json\n\nDEMO_INSTRUCTION = ${JSON.stringify(task.instruction || "")}\n\nDEMO_FINISH_SUMMARY = ${JSON.stringify(task.finish_summary || "")}\n\nDEMO_OPERATIONS = json.loads(r"""\n${opsJson}\n""")\n`;
            setScript(outputCode);
            toast.success('Script extracted!');
        } catch (err) {
            toast.error(err.response?.data?.error || 'Failed to fetch task details.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Card className="h-100 border-info">
            <Card.Header as="h6" className="d-flex align-items-center gap-2">
                🛠️ Demo Script Extractor
                <Badge bg="info" className="ms-auto text-dark">Dev Tool</Badge>
            </Card.Header>
            <Card.Body className="d-flex flex-column">
                <p className="text-muted mb-3" style={{ fontSize: '0.85rem' }}>
                    Turn a real agent run into a Demo Script. Enter a Task ID below to extract its operations into Python code.
                </p>
                <InputGroup size="sm" className="mb-3">
                    <BootstrapForm.Control
                        placeholder="Task ID (e.g. 123...)"
                        value={taskId}
                        onChange={e => setTaskId(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleExtract()}
                    />
                    <Button variant="info" onClick={handleExtract} disabled={!taskId || isLoading}>
                        {isLoading ? 'Fetching...' : 'Extract Script'}
                    </Button>
                </InputGroup>

                {script && (
                    <div className="mt-auto">
                        <div className="d-flex justify-content-between align-items-center mb-1">
                            <span className="fw-semibold small">Generated Python Code</span>
                            <Button
                                variant="outline-secondary"
                                size="sm"
                                style={{ fontSize: '0.7rem', padding: '2px 6px' }}
                                onClick={() => { navigator.clipboard.writeText(script); toast.success('Copied!'); }}
                            >
                                Copy Code
                            </Button>
                        </div>
                        <BootstrapForm.Control
                            as="textarea"
                            className="font-monospace bg-light text-dark"
                            style={{ fontSize: '0.75rem', height: '200px', resize: 'vertical' }}
                            readOnly
                            value={script}
                        />
                    </div>
                )}
            </Card.Body>
        </Card>
    );
}

function DeveloperToolsSection() {
    const toast = useToast();
    const [demoVaultId, setDemoVaultId] = useState('');
    const [resetVaultId, setResetVaultId] = useState('');
    const [snapshotFile, setSnapshotFile] = useState(null);
    const [confirmReset, setConfirmReset] = useState(false);
    const snapshotInputRef = useRef();

    const { data: vaults } = useQuery({
        queryKey: QK_ALL_VAULTS,
        queryFn: () => apiClient.get('/api/admin/vaults').then(res => res.data),
    });

    const triggerDemoMutation = useMutation({
        mutationFn: (vaultId) => apiClient.post('/api/admin/replay-test', { vault_id: parseInt(vaultId, 10) }),
        onSuccess: (res) => toast.success(`Demo task queued — task ID ${res.data.task_id}`),
        onError: (err) => toast.error(err.response?.data?.error || 'Failed to queue demo task.'),
    });

    const resetMutation = useMutation({
        mutationFn: async ({ vaultId, file }) => {
            const text = await file.text();
            const snapshot = JSON.parse(text);
            return apiClient.post(`/api/admin/vaults/${vaultId}/reset-to-snapshot`, { snapshot });
        },
        onSuccess: (res) => {
            toast.success(`Vault reset! Restored ${res.data.node_count} nodes.`);
            setSnapshotFile(null);
            setResetVaultId('');
            setConfirmReset(false);
            if (snapshotInputRef.current) snapshotInputRef.current.value = '';
        },
        onError: (err) => { toast.error(err.response?.data?.error || 'Failed to reset vault.'); setConfirmReset(false); },
    });

    const selectedVaultName = vaults?.find(v => String(v.id) === String(resetVaultId))?.name;

    return (
        <>
            <Row className="g-4 mb-4">
                {/* Tool 1: Reset from Snapshot */}
                <Col lg={6}>
                    <Card className="h-100 border-primary">
                        <Card.Header as="h6" className="d-flex align-items-center gap-2">
                            ⏪ Snapshot Reset (Manual Undo)
                            <Badge bg="primary" className="ms-auto">Dev Tool</Badge>
                        </Card.Header>
                        <Card.Body className="d-flex flex-column">
                            <p className="text-muted mb-3" style={{ fontSize: '0.85rem' }}>
                                Upload a <code>.nexidion</code> export file to wipe and restore a vault to that snapshot.
                            </p>
                            <BootstrapForm.Group className="mb-2">
                                <BootstrapForm.Label className="fw-semibold small">1. Target Vault</BootstrapForm.Label>
                                <BootstrapForm.Select size="sm" value={resetVaultId} onChange={e => setResetVaultId(e.target.value)}>
                                    <option value="">— select a vault to overwrite —</option>
                                    {vaults?.map(v => (
                                        <option key={v.id} value={v.id}>[{v.id}] {v.name} ({v.owner_username})</option>
                                    ))}
                                </BootstrapForm.Select>
                            </BootstrapForm.Group>
                            <BootstrapForm.Group className="mb-3">
                                <BootstrapForm.Label className="fw-semibold small">2. Snapshot File (.nexidion)</BootstrapForm.Label>
                                <BootstrapForm.Control
                                    size="sm"
                                    type="file"
                                    ref={snapshotInputRef}
                                    accept=".nexidion,application/json"
                                    onChange={e => setSnapshotFile(e.target.files[0])}
                                />
                            </BootstrapForm.Group>
                            <Button
                                variant="primary"
                                size="sm"
                                className="w-100 mt-auto"
                                onClick={() => setConfirmReset(true)}
                                disabled={!resetVaultId || !snapshotFile || resetMutation.isPending}
                            >
                                {resetMutation.isPending ? 'Restoring...' : 'Wipe & Restore Snapshot'}
                            </Button>
                        </Card.Body>
                    </Card>
                </Col>

                {/* Tool 2: Demo Agent Replay */}
                <Col lg={6}>
                    <Card className="h-100 border-warning">
                        <Card.Header as="h6" className="d-flex align-items-center gap-2">
                            🔁 Demo Agent Simulator
                            <Badge bg="warning" text="dark" className="ms-auto">Dev Tool</Badge>
                        </Card.Header>
                        <Card.Body className="d-flex flex-column">
                            <p className="text-muted mb-3" style={{ fontSize: '0.85rem' }}>
                                Creates a <code>pending_demo</code> task on a vault. The background runner will pick it up and execute the pre-recorded demo animation.
                            </p>
                            <BootstrapForm.Group className="mb-3">
                                <BootstrapForm.Label className="fw-semibold small">Target Vault</BootstrapForm.Label>
                                <BootstrapForm.Select size="sm" value={demoVaultId} onChange={e => setDemoVaultId(e.target.value)}>
                                    <option value="">— select a vault —</option>
                                    {vaults?.map(v => (
                                        <option key={v.id} value={v.id}>[{v.id}] {v.name} ({v.owner_username})</option>
                                    ))}
                                </BootstrapForm.Select>
                            </BootstrapForm.Group>
                            <Button
                                variant="warning"
                                size="sm"
                                className="w-100 mt-auto"
                                onClick={() => triggerDemoMutation.mutate(demoVaultId)}
                                disabled={!demoVaultId || triggerDemoMutation.isPending}
                            >
                                {triggerDemoMutation.isPending ? 'Queuing...' : '▶ Queue Demo Task'}
                            </Button>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>

            {/* Tool 3: Script Extractor */}
            <Row className="g-4 mb-4">
                <Col lg={12}>
                    <DemoScriptExtractor />
                </Col>
            </Row>

            {/* Snapshot reset confirmation modal */}
            <Modal show={confirmReset} onHide={() => setConfirmReset(false)} centered>
                <Modal.Header closeButton><Modal.Title>Confirm Snapshot Reset</Modal.Title></Modal.Header>
                <Modal.Body>
                    This will <strong>permanently wipe</strong> all nodes in vault{' '}
                    <strong>"{selectedVaultName}"</strong> and replace them with the snapshot contents.
                    This cannot be undone.
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setConfirmReset(false)}>Cancel</Button>
                    <Button
                        variant="danger"
                        disabled={resetMutation.isPending}
                        onClick={() => resetMutation.mutate({ vaultId: resetVaultId, file: snapshotFile })}
                    >
                        {resetMutation.isPending ? 'Restoring...' : 'Wipe & Restore'}
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function AdminDashboard() {
    const navigate = useNavigate();
    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);
    const lastActiveVaultId = useWorkspaceStore(state => state.lastActiveVaultId);

    const handleBackClick = () => {
        const lastPath = lastActiveVaultId ? lastValidPaths[lastActiveVaultId] : null;
        navigate(lastPath || (lastActiveVaultId ? `/vaults/${lastActiveVaultId}` : '/'));
    };

    return (
        <Container className="p-4" style={{ height: '100%', overflowY: 'auto' }}>
            <div className="d-flex justify-content-between align-items-center mb-1">
                <h1 className="mb-0">Admin Dashboard</h1>
                <Button onClick={handleBackClick} variant="secondary">Back to Workspace</Button>
            </div>
            <p className="text-muted">Manage users, vaults, and system settings.</p>

            {/* ── Users ── */}
            <h4 className="mb-3">Users</h4>
            <UsersSection />

            {/* ── Vaults ── */}
            <hr className="my-4" />
            <h4 className="mb-1">Vault Overview</h4>
            <p className="text-muted mb-3">All vaults in the system, including demo vaults owned by guest accounts.</p>
            <VaultsSection />

            {/* ── Vault Access Management ── */}
            <hr className="my-4" />
            <h4 className="mb-1">Vault Access Management</h4>
            <p className="text-muted mb-3">Assign human users and LLM agents to vaults.</p>
            <VaultAccessManager />

            {/* ── Developer Tools ── */}
            <hr className="my-4" />
            <h4 className="mb-1">Developer Tools</h4>
            <p className="text-muted mb-3">Internal testing utilities — not visible to normal users.</p>
            <DeveloperToolsSection />

        </Container>
    );
}
