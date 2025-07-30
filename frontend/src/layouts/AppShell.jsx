import React from 'react';
import { useRouteLoaderData, Link, useParams, Form, Outlet, useNavigation } from 'react-router-dom';
import { Navbar, Nav, Button, NavDropdown, Container, Spinner } from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';
import './AppShell.css'; // Ein Ort für das App-weite Styling wie Lade-Effekte

/**
 * AppShell ist die äußerste visuelle Hülle der Anwendung, die nach dem Login sichtbar ist.
 * Sie ist verantwortlich für:
 * 1. Die Anzeige der globalen Navigationsleiste (TopBar).
 * 2. Das Rendern der aktuellen Route über die <Outlet /> Komponente.
 * 3. Die Anzeige eines globalen Ladezustands.
 */
export default function AppShell() {
    // ===================================================================
    // 1. HOOKS & DATENABRUF
    // ===================================================================

    // Holt die Daten { user, vaults } vom Loader der Route mit der id: 'root'.
    // Das `|| {}` ist ein Sicherheitsnetz, falls die Daten mal nicht da sind.
    const { user, vaults } = useRouteLoaderData('root') || {};

    // Holt die aktuelle vaultId aus der URL, um den aktiven Vault zu bestimmen.
    const { vaultId } = useParams();

    // useNavigation gibt uns Informationen über den globalen Ladezustand der App.
    const navigation = useNavigation();
    const isLoading = navigation.state === 'loading';

    // ===================================================================
    // 2. ABGELEITETE DATEN & LOGIK
    // ===================================================================
    const currentVault = vaults?.find(v => v.id.toString() === vaultId);

    // ===================================================================
    // 3. RENDER-LOGIK
    // ===================================================================
    return (
        // Wir fügen eine CSS-Klasse hinzu, wenn die App lädt.
        // Nützlich, um die UI z.B. leicht auszugrauen.
        <div className={`app-shell-container ${isLoading ? 'is-loading' : ''}`}>

            {/* --- Globale Navigationsleiste --- */}
            <Navbar bg="light" variant="light" expand="lg" className="px-3 border-bottom app-shell-header">
                <Container fluid>
                    {/* Logo & Vault-Name leiten zur Basis-URL des Vaults */}
                    <Navbar.Brand as={Link} to={currentVault ? `/vaults/${currentVault.id}` : '/'}>
                        <strong>{currentVault ? `Vault: ${currentVault.name}` : 'Nexidion'}</strong>
                    </Navbar.Brand>

                    <Navbar.Toggle aria-controls="app-navbar-collapse" />
                    <Navbar.Collapse id="app-navbar-collapse">
                        <Nav className="ms-auto align-items-center">

                            {/* Vault-Wechsel-Dropdown */}
                            <NavDropdown title="Vault wechseln" id="vault-switcher-dropdown" className="me-lg-3">
                                {!vaults ? (
                                    <NavDropdown.Item disabled>
                                        <Spinner as="span" animation="border" size="sm" /> Lade...
                                    </NavDropdown.Item>
                                ) : (
                                    vaults.map(vault => (
                                        <NavDropdown.Item
                                            key={vault.id}
                                            as={Link}
                                            to={`/vaults/${vault.id}`}
                                            active={vault.id.toString() === vaultId}
                                        >
                                            {vault.name}
                                        </NavDropdown.Item>
                                    ))
                                )}
                                <NavDropdown.Divider />
                                <NavDropdown.Item as={Link} to="/vaults/create">
                                    Vaults verwalten...
                                </NavDropdown.Item>
                            </NavDropdown>

                            {/* Platzhalter für LLM-Dropdown (Logik folgt in späterer Phase) */}
                            <Nav.Link disabled className="me-lg-3">LLM: Claude Sonnet</Nav.Link>

                            {/* Logout-Button */}
                            <Form action="/logout" method="post">
                                <Button variant="outline-secondary" size="sm" type="submit">
                                    Log Out ({user?.username})
                                </Button>
                            </Form>
                        </Nav>
                    </Navbar.Collapse>
                </Container>
            </Navbar>

            {/* --- Hauptinhaltsbereich --- */}
            <main className="app-shell-content">
                {/* Hier rendert React Router die passende Kind-Komponente,
                    z.B. <WorkspaceLayout />, <SettingsPage /> oder <AdminDashboard /> */}
                <Outlet />
            </main>
        </div>
    );
}