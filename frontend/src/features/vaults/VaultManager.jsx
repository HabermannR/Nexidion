// src/features/vaults/VaultManager.jsx

import React, {useState, useEffect, useRef} from 'react';
import {Form, useLoaderData, useActionData, useNavigation, Link, useFetcher, useOutletContext} from 'react-router-dom';
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

function VaultRow({vault, activeVault, isSubmitting, vaultsCount}) {
    const fetcher = useFetcher();
    const [isEditing, setIsEditing] = useState(false);

    const isRenaming = fetcher.state === 'submitting' && fetcher.formData?.get('intent') === 'rename';
    const isDeleting = fetcher.state === 'submitting' && fetcher.formData?.get('intent') === 'delete';

    useEffect(() => {
        if (fetcher.state === 'idle') {
            setIsEditing(false);
        }
    }, [fetcher.state]);

    return (
        <tr key={vault.id}>
            {/* NAME & RENAME FORM (bleibt unverändert) */}
            <td>
                {isEditing ? (
                    <fetcher.Form method="post" className="d-flex">
                        <input type="hidden" name="intent" value="rename"/>
                        <input type="hidden" name="vaultId" value={vault.id}/>
                        <InputGroup>
                            <BootstrapForm.Control
                                type="text"
                                name="newName"
                                defaultValue={vault.name}
                                autoFocus
                                disabled={isRenaming}
                            />
                            <Button type="submit" variant="outline-success" size="sm" disabled={isRenaming}>
                                {isRenaming ? <Spinner size="sm"/> : '✓'}
                            </Button>
                            <Button variant="outline-secondary" size="sm" onClick={() => setIsEditing(false)}
                                    disabled={isRenaming}>
                                ✕
                            </Button>
                        </InputGroup>
                    </fetcher.Form>
                ) : (
                    <strong>{vault.name}</strong>
                )}
            </td>

            {/* STATUS & ACTIVATE BUTTON (bleibt unverändert) */}
            <td>
                {activeVault?.id === vault.id ? (
                    <span className="badge bg-success">Aktiv</span>
                ) : (
                    <Form method="post">
                        <input type="hidden" name="intent" value="activate"/>
                        <input type="hidden" name="vaultId" value={vault.id}/>
                        <Button type="submit" variant="outline-primary" size="sm" disabled={isSubmitting}>
                            Aktivieren
                        </Button>
                    </Form>
                )}
            </td>

            {/* ACTIONS: RENAME & DELETE */}
            <td>
                {!isEditing && (
                    <div className="btn-group" role="group">
                        <Button variant="outline-primary" size="sm" onClick={() => setIsEditing(true)}
                                disabled={isSubmitting}>
                            Umbenennen
                        </Button>

                        {/* ================= HIER IST DIE ÄNDERUNG ================= */}
                        <fetcher.Form method="post" onSubmit={(e) => {
                            if (!window.confirm(`Möchten Sie den Vault "${vault.name}" wirklich löschen?`)) {
                                e.preventDefault();
                            }
                        }}>
                            <input type="hidden" name="intent" value="delete"/>
                            <input type="hidden" name="vaultId" value={vault.id}/>
                            {/* Wir fügen die ID des aktuellen Vaults hinzu, damit die Action entscheiden kann */}
                            <input type="hidden" name="activeVaultId" value={activeVault?.id || ''}/>

                            <Button
                                type="submit"
                                variant="outline-danger"
                                size="sm"
                                disabled={isSubmitting || vaultsCount <= 1 || isDeleting}
                                title={vaultsCount <= 1 ? "Der letzte Vault kann nicht gelöscht werden" : ""}
                            >
                                {isDeleting ? <Spinner size="sm"/> : 'Löschen'}
                            </Button>
                        </fetcher.Form>
                        {/* ========================================================= */}
                    </div>
                )}
            </td>
        </tr>
    );
}

export default function VaultManager() {
    const {vaults, error: loaderError} = useLoaderData();
    const actionData = useActionData();
    const navigation = useNavigation();
    const {activeVault} = useOutletContext();

    // --- NEUE HINZUFÜGUNGEN ---
    const [isBatchMode, setIsBatchMode] = useState(false);
    const formRef = useRef(); // Ref, um das Formular programmatisch zurückzusetzen
    const inputRef = useRef(); // Ref, um den Fokus auf das Input-Feld zu setzen

    const isSubmitting = navigation.state === 'submitting';
    const isCreating = isSubmitting && (
        navigation.formData?.get('intent') === 'create' ||
        navigation.formData?.get('intent') === 'create_and_stay'
    );

    // Effekt, der das Formular leert und fokussiert, NACHDEM eine Batch-Erstellung erfolgreich war.
    useEffect(() => {
        if (
            navigation.state === 'idle' &&
            actionData?.success &&
            actionData?.intent === 'create_and_stay'
        ) {
            formRef.current?.reset(); // Formular leeren
            inputRef.current?.focus();  // Fokus zurück auf das Input-Feld
        }
    }, [actionData, navigation.state]);


    return (
        <Container className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>Vault-Verwaltung</h2>
                <Button as={Link} to={activeVault ? `/vaults/${activeVault.id}` : '/'} variant="secondary">
                    Zurück zu den Nodes
                </Button>
            </div>

            {loaderError && <Alert variant="danger">{loaderError}</Alert>}
            {actionData?.error && <Alert variant="danger">{actionData.error}</Alert>}
            {actionData?.success && <Alert variant="success">{actionData.success}</Alert>}

            <Card className="mb-4">
                <Card.Header as="h5">Neuen Vault erstellen</Card.Header>
                <Card.Body>
                    {/* Das Formular bekommt eine Ref */}
                    <Form method="post" ref={formRef}>
                        {/* Der Intent wird jetzt dynamisch gesetzt */}
                        <input type="hidden" name="intent" value={isBatchMode ? 'create_and_stay' : 'create'}/>
                        <Row>
                            <Col md={12}>
                                <BootstrapForm.Group>
                                    <BootstrapForm.Label htmlFor="new-vault-name">Vault-Name</BootstrapForm.Label>
                                    <BootstrapForm.Control
                                        id="new-vault-name"
                                        type="text"
                                        name="name"
                                        placeholder="Namen für den neuen Vault eingeben..."
                                        required
                                        disabled={isSubmitting}
                                        ref={inputRef} // Ref für den Fokus
                                        autoFocus
                                    />
                                </BootstrapForm.Group>
                            </Col>
                        </Row>
                        <Row className="mt-3">
                            <Col xs={7} md={8}>
                                {/* Die NEUE Checkbox */}
                                <BootstrapForm.Check
                                    type="switch"
                                    id="batch-mode-switch"
                                    label="Batch-Erstellung"
                                    checked={isBatchMode}
                                    onChange={(e) => setIsBatchMode(e.target.checked)}
                                    disabled={isSubmitting}
                                />
                            </Col>
                            <Col xs={5} md={4} className="d-flex align-items-end">
                                <Button type="submit" variant="primary" disabled={isSubmitting} className="w-100">
                                    {isCreating ? (
                                        <><Spinner as="span" animation="border" size="sm"/> Erstellen...</>
                                    ) : 'Vault erstellen'}
                                </Button>
                            </Col>
                        </Row>
                    </Form>
                </Card.Body>
            </Card>

            {/* EXISTING VAULTS */}
            <Card>
                <Card.Header as="h5">Bestehende Vaults</Card.Header>
                <Card.Body>
                    {vaults.length === 0 && !loaderError ? (
                        <Alert variant="info">Keine Vaults vorhanden. Erstellen Sie Ihren ersten Vault oben.</Alert>
                    ) : (
                        <Table responsive hover>
                            <thead>
                            <tr>
                                <th>Name</th>
                                <th>Status</th>
                                <th>Aktionen</th>
                            </tr>
                            </thead>
                            <tbody>
                            {vaults.map((vault) => (
                                <VaultRow
                                    key={vault.id}
                                    vault={vault}
                                    activeVault={activeVault}
                                    isSubmitting={isSubmitting}
                                    vaultsCount={vaults.length}
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