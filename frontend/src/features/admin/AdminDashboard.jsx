import React, { useState, useRef } from 'react';
import {
    Container, Card, Button, Table, Alert, Spinner, Modal,
    Form as BootstrapForm, Row, Col, InputGroup
} from 'react-bootstrap';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';
import VaultAccessManager from './VaultAccessManager';

// Helper-Komponente für das Passwort-Feld mit "Anzeigen"-Button
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

    // --- LOKALER UI-ZUSTAND ---
    const [alert, setAlert] = useState(null);
    const [modalState, setModalState] = useState({ type: null, user: null }); // 'delete', 'password'

    // --- DATENABRUF (QUERY) ---
    const { data: users, isLoading, isError, error } = useQuery({
        queryKey: ['admin', 'users'],
        queryFn: () => apiClient.get('/api/admin/users').then(res => res.data),
    });

    // --- DATENMANIPULATION (MUTATIONS) ---

    const createUserMutation = useMutation({
        mutationFn: (newUser) => apiClient.post('/api/admin/users', newUser),
        onSuccess: (data) => {
            setAlert({ type: 'success', message: `Benutzer "${data.data.username}" erfolgreich erstellt.` });
            queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
            createUserFormRef.current?.reset();
        },
        onError: (err) => {
            setAlert({ type: 'danger', message: err.response?.data?.error || 'Fehler beim Erstellen des Benutzers.' });
        }
    });

    const deleteUserMutation = useMutation({
        mutationFn: (userId) => apiClient.delete(`/api/admin/users/${userId}`),
        onSuccess: (data, userId) => {
            setAlert({ type: 'success', message: `Benutzer erfolgreich gelöscht.` });
            queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
            handleCloseModal();
        },
        onError: (err) => {
            setAlert({ type: 'danger', message: err.response?.data?.error || 'Fehler beim Löschen des Benutzers.' });
            handleCloseModal();
        }
    });

    const setPasswordMutation = useMutation({
        mutationFn: ({ userId, new_password }) => apiClient.put(`/api/admin/users/${userId}/password`, { new_password }),
        onSuccess: () => {
            setAlert({ type: 'success', message: 'Passwort erfolgreich zurückgesetzt.' });
            queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
            handleCloseModal();
        },
        onError: (err) => {
            setAlert({ type: 'danger', message: err.response?.data?.error || 'Fehler beim Setzen des Passworts.' });
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
            setAlert({ type: 'danger', message: 'Das Passwort muss mindestens 8 Zeichen lang sein.' });
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
            return <div className="text-center p-5"><Spinner animation="border" /> Lade Benutzer...</div>;
        }
        if (isError) {
            return <Alert variant="danger">Fehler beim Laden der Benutzer: {error.response?.data?.error || error.message}</Alert>;
        }
        if (!users || users.length === 0) {
            return <Alert variant="info">Keine Benutzer gefunden.</Alert>;
        }
        return (
            <Table responsive hover>
                <thead>
                <tr>
                    <th>Username</th>
                    <th>Anzeigename</th>
                    <th>Rolle</th>
                    <th>Aktionen</th>
                </tr>
                </thead>
                <tbody>
                {users.map(user => (
                    <tr key={user.id}>
                        <td><strong>{user.username}</strong></td>
                        <td>{user.display_name}</td>
                        <td>{user.is_admin ? <span className="badge bg-primary">Admin</span> : <span className="badge bg-secondary">Benutzer</span>}</td>
                        <td>
                            <Button variant="outline-secondary" size="sm" className="me-2" onClick={() => handleShowModal('password', user)}>
                                Passwort ändern
                            </Button>
                            <Button variant="outline-danger" size="sm" onClick={() => handleShowModal('delete', user)} disabled={deleteUserMutation.isPending && deleteUserMutation.variables === user.id}>
                                {deleteUserMutation.isPending && deleteUserMutation.variables === user.id ? <Spinner size="sm" /> : 'Löschen'}
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
            <p>Verwaltung von Benutzern und Systemeinstellungen.</p>

            {alert && <Alert variant={alert.type} onClose={() => setAlert(null)} dismissible>{alert.message}</Alert>}

            <Row>
                <Col lg={4} className="mb-4">
                    <Card>
                        <Card.Header as="h5">Neuen Benutzer erstellen</Card.Header>
                        <Card.Body>
                            <BootstrapForm ref={createUserFormRef} onSubmit={handleCreateUserSubmit}>
                                <BootstrapForm.Group className="mb-3" controlId="username">
                                    <BootstrapForm.Label>Username</BootstrapForm.Label>
                                    <BootstrapForm.Control type="text" name="username" required />
                                </BootstrapForm.Group>
                                <BootstrapForm.Group className="mb-3" controlId="display_name">
                                    <BootstrapForm.Label>Anzeigename</BootstrapForm.Label>
                                    <BootstrapForm.Control type="text" name="display_name" required />
                                </BootstrapForm.Group>

                                <PasswordInput name="password" label="Initiales Passwort" />

                                <BootstrapForm.Check
                                    type="switch"
                                    id="is_admin_switch"
                                    name="is_admin"
                                    label="Zum Administrator machen"
                                    className="mb-3"
                                />

                                <div className="d-grid">
                                    <Button variant="primary" type="submit" disabled={createUserMutation.isPending}>
                                        {createUserMutation.isPending ? <><Spinner size="sm" /> Erstellen...</> : 'Benutzer erstellen'}
                                    </Button>
                                </div>
                            </BootstrapForm>
                        </Card.Body>
                    </Card>
                </Col>
                <Col lg={8}>
                    <Card>
                        <Card.Header as="h5">Bestehende Benutzer</Card.Header>
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

            {/* Löschen-Bestätigungs-Modal */}
            <Modal show={modalState.type === 'delete'} onHide={handleCloseModal} centered>
                <Modal.Header closeButton>
                    <Modal.Title>Benutzer löschen</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    Möchten Sie den Benutzer "<strong>{modalState.user?.username}</strong>" wirklich endgültig löschen? Diese Aktion kann nicht rückgängig gemacht werden.
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={handleCloseModal}>Abbrechen</Button>
                    <Button variant="danger" onClick={handleDeleteConfirm} disabled={deleteUserMutation.isPending}>
                        {deleteUserMutation.isPending ? 'Löschen...' : 'Endgültig löschen'}
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Passwort-Ändern-Modal */}
            <Modal show={modalState.type === 'password'} onHide={handleCloseModal} centered>
                <BootstrapForm ref={passwordFormRef} onSubmit={handleSetPasswordSubmit}>
                    <Modal.Header closeButton>
                        <Modal.Title>Passwort zurücksetzen für {modalState.user?.username}</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <PasswordInput name="new_password" label="Neues Passwort" />
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={handleCloseModal}>Abbrechen</Button>
                        <Button variant="primary" type="submit" disabled={setPasswordMutation.isPending}>
                            {setPasswordMutation.isPending ? 'Speichern...' : 'Passwort speichern'}
                        </Button>
                    </Modal.Footer>
                </BootstrapForm>
            </Modal>
        </Container>
    );
}