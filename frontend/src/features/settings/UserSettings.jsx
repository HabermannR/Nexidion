// src/features/settings/UserSettings.jsx

import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Container, Card, Button, Form as BootstrapForm, Row, Col, Alert, Spinner } from 'react-bootstrap';
import apiClient from '../../api/apiClient';
import { useWorkspaceStore } from '../workspace/workspaceStore';

export default function UserSettings() {
    const formRef = useRef();
    const navigate = useNavigate();

    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);
    const lastActiveVaultId = useWorkspaceStore(state => state.lastActiveVaultId);

    // --- LOCAL UI STATE ---
    const [alert, setAlert] = useState(null);

    // --- DATA MUTATION ---
    const changePasswordMutation = useMutation({
        mutationFn: (passwords) => apiClient.post('/api/auth/change-password', passwords),
        onSuccess: () => {
            setAlert({type: 'success', message: 'Password changed successfully.'});
            formRef.current?.reset();
        },
        onError: (err) => {
            setAlert({type: 'danger', message: err.response?.data?.error || 'An error occurred.'});
        }
    });

    // --- EVENT HANDLERS ---
    const handleSubmit = (e) => {
        e.preventDefault();
        setAlert(null);

        const formData = new FormData(e.currentTarget);
        const old_password = formData.get('old_password');
        const new_password = formData.get('new_password');
        const confirm_password = formData.get('confirm_password');

        if (new_password !== confirm_password) {
            setAlert({type: 'danger', message: 'The new passwords do not match.'});
            return;
        }

        if (!old_password || !new_password) {
            setAlert({type: 'danger', message: 'Please fill in all fields.'});
            return;
        }

        changePasswordMutation.mutate({ old_password, new_password });
    };

    // Navigate back to the last visited node, or fall back to the vault root, or the app root.
    const handleBackClick = () => {
        const lastPath = lastActiveVaultId ? lastValidPaths[lastActiveVaultId] : null;
        navigate(lastPath || (lastActiveVaultId ? `/vaults/${lastActiveVaultId}` : '/'));
    };

    return (
        <Container className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>User Settings</h2>
                {/* Back button navigates to the last visited vault location */}
                <Button onClick={handleBackClick} variant="secondary">
                    Back to Workspace
                </Button>
            </div>

            {alert && <Alert variant={alert.type} onClose={() => setAlert(null)} dismissible>{alert.message}</Alert>}

            <Row>
                <Col md={8} lg={6}>
                    <Card>
                        <Card.Header as="h5">Change Password</Card.Header>
                        <Card.Body>
                            <BootstrapForm ref={formRef} onSubmit={handleSubmit}>
                                <BootstrapForm.Group className="mb-3" controlId="old_password">
                                    <BootstrapForm.Label>Current Password</BootstrapForm.Label>
                                    <BootstrapForm.Control type="password" name="old_password" required />
                                </BootstrapForm.Group>

                                <BootstrapForm.Group className="mb-3" controlId="new_password">
                                    <BootstrapForm.Label>New Password</BootstrapForm.Label>
                                    <BootstrapForm.Control type="password" name="new_password" required />
                                </BootstrapForm.Group>

                                <BootstrapForm.Group className="mb-3" controlId="confirm_password">
                                    <BootstrapForm.Label>Confirm New Password</BootstrapForm.Label>
                                    <BootstrapForm.Control type="password" name="confirm_password" required />
                                </BootstrapForm.Group>

                                <div className="d-flex justify-content-end">
                                    <Button variant="primary" type="submit" disabled={changePasswordMutation.isPending}>
                                        {changePasswordMutation.isPending ? <><Spinner size="sm"/> Saving...</> : 'Change Password'}
                                    </Button>
                                </div>
                            </BootstrapForm>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>
        </Container>
    );
}