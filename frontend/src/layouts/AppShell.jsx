import React, { useEffect } from 'react'; // useCallback is not strictly needed but good practice for clarity
import { Link, useLocation, useParams, Form, Outlet, useNavigation } from 'react-router-dom';
import { Navbar, Nav, Button, NavDropdown, Container, Spinner } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import { useWorkspaceStore } from '../features/workspace/workspaceStore';
import apiClient from '../api/apiClient';
import 'bootstrap/dist/css/bootstrap.min.css';
import './AppShell.css';
import { useUser } from '../features/auth/useUser';

export default function AppShell() {
    const { data: vaults, isLoading: isLoadingVaults } = useQuery({
        queryKey: ['allVaults'],
        queryFn: () => apiClient.get('/api/vaults/').then(res => res.data),
    });
    const { data: user, isLoading: isLoadingUser } = useUser();
    const { vaultId, nodeId } = useParams();
    const navigation = useNavigation();
    const setLastValidWorkspacePath = useWorkspaceStore(state => state.setLastValidWorkspacePath);
    const location = useLocation();

    // --- START: LLM INITIALIZATION LOGIC (FIXED) ---

    // 1. Select the ACTION and the STATE in two separate, granular hooks.
    // Actions selected this way have a stable identity.

    const initializeModels = useWorkspaceStore((state) => state.initializeModels);
    const chatModel = useWorkspaceStore((state) => state.chatModel);

    const { data: availableLlms } = useQuery({
        queryKey: ['llmModels'],
        queryFn: () => apiClient.get('/api/llm/models').then(res => res.data),
        staleTime: Infinity,
    });

    useEffect(() => {
        if (availableLlms) {
            initializeModels(availableLlms);
        }
    }, [availableLlms, initializeModels]);

    // --- END: LLM INITIALIZATION LOGIC ---

    const isLoading = navigation.state === 'loading' || isLoadingVaults || isLoadingUser;
    const currentVault = vaults?.find(v => v.id.toString() === vaultId);

    useEffect(() => {
        // Wir speichern den Pfad nur, wenn er einen gültigen Node enthält.
        // Pfade wie `/vaults/projekt-x` ohne Node-ID wollen wir nicht speichern.
        if (vaultId && nodeId) {
            setLastValidWorkspacePath(location.pathname);
        }
    }, [vaultId, nodeId, location.pathname, setLastValidWorkspacePath]);

    return (
        <div className={`app-shell-container ${isLoading ? 'is-loading' : ''}`}>
            <Navbar bg="light" variant="light" expand="lg" className="px-3 border-bottom app-shell-header">
                <Container fluid>
                    <Navbar.Brand as={Link} to={currentVault ? `/vaults/${currentVault.id}` : '/'}>
                        <strong>{currentVault ? `${currentVault.name}` : 'Nexidion'}</strong>
                    </Navbar.Brand>
                    <Navbar.Toggle aria-controls="app-navbar-collapse" className="navbar-toggler-sm" />
                    <Navbar.Collapse id="app-navbar-collapse">
                        <Nav className="ms-auto align-items-center">
                            {/* Vault Switcher Dropdown (unchanged) */}
                            <NavDropdown title="Vault wechseln" id="vault-switcher-dropdown" className="me-lg-3">
                                <div className="scrollable-dropdown">
                                    {isLoadingVaults ? (
                                        <NavDropdown.Item disabled>
                                            <Spinner as="span" animation="border" size="sm" /> Lade...
                                        </NavDropdown.Item>
                                    ) : (
                                        vaults?.map(vault => (
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
                                </div>
                                <NavDropdown.Divider />
                                <NavDropdown.Item as={Link} to="/settings/vaults">
                                    Vaults verwalten...
                                </NavDropdown.Item>
                            </NavDropdown>

                            {/* --- NEW, SEPARATE LLM DROPDOWN --- */}

                            <NavDropdown
                                title={`LLM: ${chatModel?.name || '...'}`}
                                id="llm-settings-dropdown"
                                className="me-lg-2"
                            >
                                <NavDropdown.Item as={Link} to="/settings/llms">
                                    Modelle verwalten...
                                </NavDropdown.Item>
                            </NavDropdown>

                            {/* --- USER DROPDOWN (CLEANED UP) --- */}
                            <NavDropdown
                                title={user?.username || 'Account'}
                                id="user-settings-dropdown"
                                align="end"
                                className="me-lg-2"
                            >
                                <NavDropdown.Item as={Link} to="/settings/user">
                                    Benutzereinstellungen
                                </NavDropdown.Item>
                                <NavDropdown.Divider />
                                <NavDropdown.ItemText>
                                    <Form action="/logout" method="post" className="d-grid">
                                        <Button variant="outline-danger" size="sm" type="submit">
                                            Log Out
                                        </Button>
                                    </Form>
                                </NavDropdown.ItemText>
                            </NavDropdown>

                        </Nav>
                    </Navbar.Collapse>
                </Container>
            </Navbar>

            <main className="app-shell-content">
                <Outlet context={{ activeVault: currentVault }} />
            </main>
        </div>
    );
}