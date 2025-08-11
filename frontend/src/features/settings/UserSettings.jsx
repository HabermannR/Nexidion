// src/features/settings/UserSettings.jsx

import React, { useState, useRef } from 'react';
// KORREKTUR: useParams importieren, um den Kontext zu bestimmen, falls outlet-context fehlt.
import { useOutletContext, useNavigate, useParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Container, Card, Button, Form as BootstrapForm, Row, Col, Alert, Spinner } from 'react-bootstrap';
import apiClient from '../../api/apiClient';
// KORREKTUR: Den Workspace-Store importieren, um das vault-spezifische Pfad-Objekt zu lesen.
import { useWorkspaceStore } from '../workspace/workspaceStore';

export default function UserSettings() {
    // KORREKTUR: useOutletContext ist nicht immer zuverlässig, useParams als Fallback nutzen.
    const { activeVault } = useOutletContext() || {};
    // Der vaultId aus der URL gibt uns den Kontext, aus dem wir gekommen sind.
    const { vaultId } = useParams();
    const formRef = useRef();
    const navigate = useNavigate();

    // KORREKTUR: Das vault-spezifische Pfad-Objekt lesen, nicht eine einzelne Variable.
    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);

    // KORREKTUR: Den korrekten Pfad für den aktuellen Vault-Kontext ermitteln.
    // Wir priorisieren den `activeVault` aus dem Context, nehmen aber die URL-Param als Fallback.
    const currentVaultId = activeVault?.id || vaultId;
    const lastValidPathForThisVault = lastValidPaths ? lastValidPaths[currentVaultId] : null;

    // --- LOKALER UI-ZUSTAND ---
    const [alert, setAlert] = useState(null);

    // --- DATA MUTATION ---
    const changePasswordMutation = useMutation({
        mutationFn: (passwords) => apiClient.post('/api/auth/change-password', passwords),
        onSuccess: () => {
            setAlert({type: 'success', message: 'Passwort erfolgreich geändert.'});
            formRef.current?.reset();
        },
        onError: (err) => {
            setAlert({type: 'danger', message: err.response?.data?.error || 'Ein Fehler ist aufgetreten.'});
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
            setAlert({type: 'danger', message: 'Die neuen Passwörter stimmen nicht überein.'});
            return;
        }

        if (!old_password || !new_password) {
            setAlert({type: 'danger', message: 'Bitte füllen Sie alle Felder aus.'});
            return;
        }

        changePasswordMutation.mutate({ old_password, new_password });
    };

    // KORREKTUR: Handler für den Zurück-Button, der den vault-spezifischen Pfad nutzt.
    const handleBackClick = () => {
        // Nutze den gespeicherten Pfad. Wenn keiner da ist, nimm den Fallback zum Vault-Root.
        // Der finale Fallback zu '/' fängt den seltenen Fall ab, dass kein Vault-Kontext existiert.
        navigate(lastValidPathForThisVault || (currentVaultId ? `/vaults/${currentVaultId}` : '/'));
    };

    return (
        <Container className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>Benutzereinstellungen</h2>
                {/* KORREKTUR: Der Button nutzt jetzt den korrigierten onClick-Handler */}
                <Button onClick={handleBackClick} variant="secondary">
                    Zurück zum Workspace
                </Button>
            </div>

            {alert && <Alert variant={alert.type} onClose={() => setAlert(null)} dismissible>{alert.message}</Alert>}

            <Row>
                <Col md={8} lg={6}>
                    <Card>
                        <Card.Header as="h5">Passwort ändern</Card.Header>
                        <Card.Body>
                            <BootstrapForm ref={formRef} onSubmit={handleSubmit}>
                                <BootstrapForm.Group className="mb-3" controlId="old_password">
                                    <BootstrapForm.Label>Aktuelles Passwort</BootstrapForm.Label>
                                    <BootstrapForm.Control type="password" name="old_password" required />
                                </BootstrapForm.Group>

                                <BootstrapForm.Group className="mb-3" controlId="new_password">
                                    <BootstrapForm.Label>Neues Passwort</BootstrapForm.Label>
                                    <BootstrapForm.Control type="password" name="new_password" required />
                                </BootstrapForm.Group>

                                <BootstrapForm.Group className="mb-3" controlId="confirm_password">
                                    <BootstrapForm.Label>Neues Passwort bestätigen</BootstrapForm.Label>
                                    <BootstrapForm.Control type="password" name="confirm_password" required />
                                </BootstrapForm.Group>

                                <div className="d-flex justify-content-end">
                                    <Button variant="primary" type="submit" disabled={changePasswordMutation.isPending}>
                                        {changePasswordMutation.isPending ? <><Spinner size="sm"/> Speichern...</> : 'Passwort ändern'}
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