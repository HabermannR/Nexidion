// src/layouts/AppShell.jsx (NEU)

import React, { useEffect } from 'react';
import { Link, useLocation, useParams, Outlet } from 'react-router-dom';
import { Navbar, Nav, Button, NavDropdown, Container, Spinner } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';

// V4-ÄNDERUNG: Wir importieren unseren neuen Logout-Hook
import { useLogoutMutation } from '../features/auth/useLogoutMutation.js';

import { useWorkspaceStore } from '../features/workspace/workspaceStore';
import apiClient from '../api/apiClient';
import 'bootstrap/dist/css/bootstrap.min.css';
import './AppShell.css';

// Die Logik für den User und die Vaults bleibt fast gleich, sie ist schon gutes V4.
const useUserQuery = () => useQuery({
    queryKey: ['user'],
    queryFn: () => apiClient.get('/api/auth/me').then(res => res.data)
});

const useVaultsQuery = () => useQuery({
    queryKey: ['allVaults'],
    queryFn: () => apiClient.get('/api/vaults/').then(res => res.data),
});


export default function AppShell() {
    const { data: vaults, isLoading: isLoadingVaults } = useVaultsQuery();
    const { data: user, isLoading: isLoadingUser } = useUserQuery();

    // V4-ÄNDERUNG: Wir holen uns die Logout-Funktion von unserem Hook
    const { mutate: logout } = useLogoutMutation();

    const { vaultId, nodeId } = useParams();
    const location = useLocation();

    // Zustand aus dem Store, das bleibt gleich (Zustand ist für UI-State da)
    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);
    const setLastValidPathForVault = useWorkspaceStore(state => state.setLastValidPathForVault);
    const chatModel = useWorkspaceStore((state) => state.chatModel);

    // V4-ÄNDERUNG: Der Ladezustand ist jetzt sauber und explizit.
    // Der unpräzise `navigation.state` ist entfernt.
    const isLoading = isLoadingVaults || isLoadingUser;

    // V4-ÄNDERUNG: Die 'useLlmModels'-Aufrufe sind entfernt. AppShell ist nicht dafür zuständig.

    const currentVault = vaults?.find(v => v.id.toString() === vaultId);

    // Der useEffect bleibt gleich, seine Logik ist korrekt.
    useEffect(() => {
        if (vaultId && nodeId) {
            setLastValidPathForVault(vaultId, location.pathname);
        }
    }, [vaultId, nodeId, location.pathname, setLastValidPathForVault]);

    const getVaultLink = (targetVaultId) => {
        return lastValidPaths[targetVaultId] || `/vaults/${targetVaultId}`;
    };

    return (
        <div className={`app-shell-container ${isLoading ? 'is-loading' : ''}`}>
            <Navbar bg="light" variant="light" expand="lg" className="px-3 border-bottom app-shell-header">
                <Container fluid>
                    {/* ... Der Rest der Navbar bleibt fast gleich ... */}
                    <Navbar.Brand as={Link} to={currentVault ? `/vaults/${currentVault.id}` : '/'}>
                        <strong>{currentVault ? `${currentVault.name}` : 'Nexidion'}</strong>
                    </Navbar.Brand>
                    <Navbar.Toggle aria-controls="app-navbar-collapse" className="navbar-toggler-sm" />
                    <Navbar.Collapse id="app-navbar-collapse">
                        <Nav className="ms-auto align-items-center">
                            {/* ... Vault Switcher ... */}
                            <NavDropdown title="Vault wechseln" id="vault-switcher-dropdown" className="me-lg-3">
                                <div className="scrollable-dropdown">
                                    {isLoadingVaults ? (
                                        <NavDropdown.Item disabled>...</NavDropdown.Item>
                                    ) : (
                                        vaults?.map(vault => (
                                            <NavDropdown.Item key={vault.id} as={Link} to={getVaultLink(vault.id)} active={vault.id.toString() === vaultId}>
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

                            {/* ... LLM Dropdown ... */}
                            <NavDropdown title={`LLM: ${chatModel?.name || '...'}`} id="llm-settings-dropdown" className="me-lg-2">
                                <NavDropdown.Item as={Link} to="/settings/llms">
                                    Modelle verwalten...
                                </NavDropdown.Item>
                            </NavDropdown>

                            {/* ... User Dropdown ... */}
                            <NavDropdown title={user?.username || 'Account'} id="user-settings-dropdown" align="end" className="me-lg-2">
                                <NavDropdown.Item as={Link} to="/settings/user">
                                    Benutzereinstellungen
                                </NavDropdown.Item>
                                <NavDropdown.Divider />
                                <NavDropdown.ItemText>
                                    {/* --- V4-ÄNDERUNG: Der Logout-Button --- */}
                                    {/* Keine <Form> mehr. Nur ein Button, der unsere Hook-Funktion aufruft. */}
                                    <div className="d-grid">
                                        <Button variant="outline-danger" size="sm" onClick={() => logout()}>
                                            Log Out
                                        </Button>
                                    </div>
                                </NavDropdown.ItemText>
                            </NavDropdown>
                        </Nav>
                    </Navbar.Collapse>
                </Container>
            </Navbar>

            <main className="app-shell-content">
                {/* V4-ÄNDERUNG (Die Kür): Wir entfernen den 'context'. Die Kinder holen ihre Daten selbst. */}
                <Outlet />
            </main>
        </div>
    );
}