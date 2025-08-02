import React from 'react';
import {useRouteLoaderData, Link, useParams, Form, Outlet, useNavigation} from 'react-router-dom';
import {Navbar, Nav, Button, NavDropdown, Container, Spinner} from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';
import './AppShell.css';

/**
 * AppShell ist die äußerste visuelle Hülle der Anwendung, die nach dem Login sichtbar ist.
 * Sie ist verantwortlich für:
 * 1. Die Anzeige der globalen Navigationsleiste (TopBar).
 * 2. Das Rendern der aktuellen Route über die <Outlet /> Komponente.
 * 3. Die Anzeige eines globalen Ladezustands.
 */
export default function AppShell() {
    const {user, vaults} = useRouteLoaderData('root') || {};
    const {vaultId} = useParams();
    const navigation = useNavigation();
    const isLoading = navigation.state === 'loading';

    const currentVault = vaults?.find(v => v.id.toString() === vaultId);

    return (
        <div className={`app-shell-container ${isLoading ? 'is-loading' : ''}`}>
            <Navbar bg="light" variant="light" expand="lg" className="px-3 border-bottom app-shell-header">
                <Container fluid>
                    <Navbar.Brand as={Link} to={currentVault ? `/vaults/${currentVault.id}` : '/'}>
                        <strong>{currentVault ? `${currentVault.name}` : 'Nexidion'}</strong>
                    </Navbar.Brand>
                    <Navbar.Toggle aria-controls="app-navbar-collapse" className="navbar-toggler-sm"/>
                    <Navbar.Collapse id="app-navbar-collapse">
                        <Nav className="ms-auto align-items-center">
                            <NavDropdown title="Vault wechseln" id="vault-switcher-dropdown" className="me-lg-3">
                                {!vaults ? (
                                    <NavDropdown.Item disabled>
                                        <Spinner as="span" animation="border" size="sm"/> Lade...
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
                                <NavDropdown.Divider/>
                                <NavDropdown.Item as={Link} to="/settings/vaults">
                                    Vaults verwalten...
                                </NavDropdown.Item>
                            </NavDropdown>
                            <Nav.Link disabled className="me-lg-3">LLM: Claude Sonnet</Nav.Link>
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
                <Outlet context={{activeVault: currentVault}}/>
            </main>
        </div>
    );
}