import React, { useState, useRef } from 'react';
import {
    Container, Card, Button, Table, Alert, Spinner, Modal,
    Form as BootstrapForm, Row, Col, InputGroup
} from 'react-bootstrap';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';
import VaultAccessManager from './VaultAccessManager';

// Helper component for the password field with a "Show" button
function PasswordInput({ name, label, required = true }) {
    const [showPassword, setShowPassword] = useState(false);
    return (
        <BootstrapForm.Group className="mb-3" controlId={name}>
            <BootstrapForm.Label>{label}</BootstrapForm.Label>
            <InputGroup>
                <BootstrapForm.Control type={showPassword ? 'text' : 'password'} name={name} required={required} />
                <Button variant="outline-secondary" onClick={() => setShowPassword(!showPassword)}>
                    {showPassword ? 'Hide' : 'Show'}
                </Button>
            </InputGroup>
        </BootstrapForm.Group>
    );
}

export default function AdminDashboard() {
    const queryClient = useQueryClient();
    const createUserFormRef = useRef();
    const passwordFormRef = useRef();

    // --- LOCAL UI STATE ---
    const [alert, setAlert] = useState(null);
    const [modalState, setModalState] = useState({ type: null, user: null }); // 'delete', 'password'

    // --- DATA FETCHING (QUERY) ---
    const { data: users, isLoading, isError, error } = useQuery({
        queryKey: ['admin', 'users'],
        queryFn: () => apiClient.get('/api/admin/users').then(res => res.data),
    });

    // --- DATA MANIPULATION (MUTATIONS) ---

    const createUserMutation = useMutation({
        mutationFn: (newUser) => apiClient.post('/api/admin/users', newUser),
        onSuccess: (data) => {
            setAlert({ type: 'success', message: `User "${data.data.username}" successfully created.` });
            queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
            createUserFormRef.current?.reset();
        },
        onError: (err) => {
            setAlert({ type: 'danger', message: err.response?.data?.error || 'Error creating user.' });
        }
    });

    const deleteUserMutation = useMutation({
        mutationFn: (userId) => apiClient.delete(`/api/admin/users/${userId}`),
        onSuccess: () => {
            setAlert({ type: 'success', message: `User successfully deleted.` });
            queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
            handleCloseModal();
        },
        onError: (err) => {
            setAlert({ type: 'danger', message: err.response?.data?.error || 'Error deleting user.' });
            handleCloseModal();
        }
    });

    const setPasswordMutation = useMutation({
        mutationFn: ({ userId, new_password }) => apiClient.put(`/api/admin/users/${userId}/password`, { new_password }),
        onSuccess: () => {
            setAlert({ type: 'success', message: 'Password successfully reset.' });
            queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
            passwordFormRef.current?.reset();
            handleCloseModal();
        },
        onError: (err) => {
            setAlert({ type: 'danger', message: err.response?.data?.error || 'Error setting password.' });
        }
    });

    // --- EVENT HANDLERS ---
    const handleCreateUserSubmit = (e) => {
        e.preventDefault();
        setAlert(null);
        const formData = new FormData(e.currentTarget);
        const newUser = {
            username: formData.get('username'),
            display_name: formData.get('display_name'),
            password: formData.get('password'),
            is_admin: formData.get('is_admin') === 'on'
        };
        createUserMutation.mutate(newUser);
    };

    const handleSetPasswordSubmit = (e) => {
        e.preventDefault();
        setAlert(null);
        const formData = new FormData(e.currentTarget);
        const new_password = formData.get('new_password');

        if (new_password && new_password.length >= 8) {
            setPasswordMutation.mutate({ userId: modalState.user.id, new_password });
        } else {
            setAlert({ type: 'danger', message: 'The password must be at least 8 characters long.' });
        }
    };

    const handleDeleteConfirm = () => {
        if (modalState.user) {
            deleteUserMutation.mutate(modalState.user.id);
        }
    };

    const handleShowModal = (type, user) => setModalState({ type, user });
    const handleCloseModal = () => setModalState({ type: null, user: null });


    // --- RENDERING ---
    const renderContent = () => {
        if (isLoading) {
            return <div className="text-center p-5"><Spinner animation="border" /> Loading users...</div>;
        }
        if (isError) {
            return <Alert variant="danger">Error loading users: {error.response?.data?.error || error.message}</Alert>;
        }
        if (!users || users.length === 0) {
            return <Alert variant="info">No users found.</Alert>;
        }
        return (
            <Table responsive hover>
                <thead>
                <tr>
                    <th>Username</th>
                    <th>Display Name</th>
                    <th>Role</th>
                    <th>Actions</th>
                </tr>
                </thead>
                <tbody>
                {users.map(user => (
                    <tr key={user.id}>
                        <td><strong>{user.username}</strong></td>
                        <td>{user.display_name}</td>
                        <td>{user.is_admin ? <span className="badge bg-primary">Admin</span> : <span className="badge bg-secondary">User</span>}</td>
                        <td>
                            <Button variant="outline-secondary" size="sm" className="me-2" onClick={() => handleShowModal('password', user)}>
                                Change Password
                            </Button>
                            <Button variant="outline-danger" size="sm" onClick={() => handleShowModal('delete', user)} disabled={deleteUserMutation.isPending && Number(deleteUserMutation.variables) === Number(user.id)}>
                                {deleteUserMutation.isPending && Number(deleteUserMutation.variables) === Number(user.id) ? <Spinner size="sm" /> : 'Delete'}
                            </Button>
                        </td>
                    </tr>
                ))}
                </tbody>
            </Table>
        );
    };

    return (
        <Container className="p-4" style={{ height: '100%', overflowY: 'auto' }}>
            <h1>Admin Dashboard</h1>
            <p>Management of users and system settings.</p>

            {alert && <Alert variant={alert.type} onClose={() => setAlert(null)} dismissible>{alert.message}</Alert>}

            <Row>
                <Col lg={4} className="mb-4">
                    <Card>
                        <Card.Header as="h5">Create New User</Card.Header>
                        <Card.Body>
                            <BootstrapForm ref={createUserFormRef} onSubmit={handleCreateUserSubmit}>
                                <BootstrapForm.Group className="mb-3" controlId="username">
                                    <BootstrapForm.Label>Username</BootstrapForm.Label>
                                    <BootstrapForm.Control type="text" name="username" required />
                                </BootstrapForm.Group>
                                <BootstrapForm.Group className="mb-3" controlId="display_name">
                                    <BootstrapForm.Label>Display Name</BootstrapForm.Label>
                                    <BootstrapForm.Control type="text" name="display_name" required />
                                </BootstrapForm.Group>

                                <PasswordInput name="password" label="Initial Password" />

                                <BootstrapForm.Check
                                    type="switch"
                                    id="is_admin_switch"
                                    name="is_admin"
                                    label="Make administrator"
                                    className="mb-3"
                                />

                                <div className="d-grid">
                                    <Button variant="primary" type="submit" disabled={createUserMutation.isPending}>
                                        {createUserMutation.isPending ? <><Spinner size="sm" /> Creating...</> : 'Create User'}
                                    </Button>
                                </div>
                            </BootstrapForm>
                        </Card.Body>
                    </Card>
                </Col>
                <Col lg={8}>
                    <Card>
                        <Card.Header as="h5">Existing Users</Card.Header>
                        <Card.Body className="p-0">
                            {renderContent()}
                        </Card.Body>
                    </Card>
                </Col>
            </Row>

            {/* --- Vault Access Management --- */}
            <hr className="my-4" />
            <h4 className="mb-1">Vault Access Management</h4>
            <p className="text-muted">Assign human users and LLM agents to vaults.</p>
            <VaultAccessManager />

            {/* --- Modals --- */}

            {/* Delete Confirmation Modal */}
            <Modal show={modalState.type === 'delete'} onHide={handleCloseModal} centered>
                <Modal.Header closeButton>
                    <Modal.Title>Delete User</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    Are you sure you want to permanently delete the user "<strong>{modalState.user?.username}</strong>"? This action cannot be undone.
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={handleCloseModal}>Cancel</Button>
                    <Button variant="danger" onClick={handleDeleteConfirm} disabled={deleteUserMutation.isPending}>
                        {deleteUserMutation.isPending ? 'Deleting...' : 'Delete permanently'}
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Change Password Modal */}
            <Modal show={modalState.type === 'password'} onHide={handleCloseModal} centered>
                <BootstrapForm ref={passwordFormRef} onSubmit={handleSetPasswordSubmit}>
                    <Modal.Header closeButton>
                        <Modal.Title>Reset password for {modalState.user?.username}</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <PasswordInput name="new_password" label="New Password" />
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={handleCloseModal}>Cancel</Button>
                        <Button variant="primary" type="submit" disabled={setPasswordMutation.isPending}>
                            {setPasswordMutation.isPending ? 'Saving...' : 'Save Password'}
                        </Button>
                    </Modal.Footer>
                </BootstrapForm>
            </Modal>
        </Container>
    );
}