import React from 'react';
// NEU: Importiere die Form-Komponente und Hooks von React Router
import { Form, useActionData } from 'react-router-dom';
import { Container, Card, Button, Form as BootstrapForm, Alert } from 'react-bootstrap';

export default function VaultCreationPage() {
    // Holt sich eventuelle Fehler von der Action zurück
    const actionData = useActionData();

    return (
        <Container className="pt-5" style={{ maxWidth: '600px' }}>
            <Card>
                <Card.Body>
                    <Card.Title as="h2" className="text-center">Willkommen!</Card.Title>
                    <Card.Text className="text-center text-muted mb-4">
                        Erstelle deinen ersten Vault, um mit der Arbeit zu beginnen.
                    </Card.Text>

                    {/* Wir verwenden die <Form> von React Router */}
                    <Form method="post">
                        <BootstrapForm.Group className="mb-3">
                            <BootstrapForm.Label>Name des Vaults</BootstrapForm.Label>
                            <BootstrapForm.Control
                                type="text"
                                placeholder="z.B. Mein Projekt"
                                name="vaultName" // WICHTIG: Der Name für die Formulardaten
                                required
                                autoFocus
                            />
                        </BootstrapForm.Group>

                        {actionData?.error && (
                            <Alert variant="danger">{actionData.error}</Alert>
                        )}

                        <div className="d-grid">
                            <Button variant="primary" size="lg" type="submit">
                                Vault erstellen
                            </Button>
                        </div>
                    </Form>
                </Card.Body>
            </Card>
        </Container>
    );
}