// src/features/settings/UserSettings.jsx

import React, { useState, useRef } from 'react';
// FIX: Import useParams to determine the context in case outlet-context is missing.
import { useOutletContext, useNavigate, useParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Container, Card, Button, Form as BootstrapForm, Row, Col, Alert, Spinner } from 'react-bootstrap';
import apiClient from '../../api/apiClient';
// FIX: Import the Workspace store to read the vault-specific path object.
import { useWorkspaceStore } from '../workspace/workspaceStore';

export default function UserSettings() {
    // FIX: useOutletContext is not always reliable, use useParams as a fallback.
    const { activeVault } = useOutletContext() || {};
    // The vaultId from the URL gives us the context we came from.
    const { vaultId } = useParams();
    const formRef = useRef();
    const navigate = useNavigate();

    // FIX: Read the vault-specific path object, not a single variable.
    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);

    // FIX: Determine the correct path for the current vault context.
    // We prioritize the `activeVault` from the context, but take the URL param as a fallback.
    const currentVaultId = activeVault?.id || vaultId;
    const lastValidPathForThisVault = lastValidPaths ? lastValidPaths[currentVaultId] : null;

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

    // FIX: Handler for the back button that uses the vault-specific path.
    const handleBackClick = () => {
        // Use the saved path. If there is none, use the fallback to the vault root.
        // The final fallback to '/' handles the rare case where no vault context exists.
        navigate(lastValidPathForThisVault || (currentVaultId ? `/vaults/${currentVaultId}` : '/'));
    };

    return (
        <Container className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>User Settings</h2>
                {/* FIX: The button now uses the corrected onClick handler */}
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