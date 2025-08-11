// src/layouts/AppShell.jsx

import React, { useEffect } from 'react';
import { Link, useLocation, useParams, Outlet } from 'react-router-dom';
import { Navbar, Nav, Button, NavDropdown, Container } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';

import { useLogoutMutation } from '../features/auth/useLogoutMutation.js';
import { useWorkspaceStore } from '../features/workspace/workspaceStore';
import apiClient from '../api/apiClient';
import 'bootstrap/dist/css/bootstrap.min.css';
import './AppShell.css';

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
    const { mutate: logout } = useLogoutMutation();
    const { vaultId, nodeId } = useParams();
    const location = useLocation();

    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);
    const setLastValidPathForVault = useWorkspaceStore(state => state.setLastValidPathForVault);
    const chatModel = useWorkspaceStore((state) => state.chatModel);

    const isLoading = isLoadingVaults || isLoadingUser;
    const currentVault = vaults?.find(v => v.id.toString() === vaultId);

    useEffect(() => {
        // Dieser Hook speichert den "Rückkehrpunkt", aber NUR, wenn wir im Workspace sind.
        if (vaultId && nodeId) {
            setLastValidPathForVault(vaultId, location.pathname);
        }
    }, [vaultId, nodeId, location.pathname, setLastValidPathForVault]);

    const getVaultLink = (targetVaultId) => {
        return lastValidPaths[targetVaultId] || `/vaults/${targetVaultId}`;
    };

    const llmSettingsPath = currentVault
        ? `/settings/llms?vaultId=${currentVault.id}`
        // Fallback, wenn wir uns außerhalb eines Vault-Kontexts befinden (z.B. auf /settings/vaults)
        // und keinen currentVault haben. In diesem Fall ist der Link ohnehin deaktiviert.
        : '/settings/llms';

    // KORREKTUR: Wir prüfen, ob wir uns auf IRGENDEINER Einstellungsseite befinden.
    const isOnAnySettingsPage = location.pathname.startsWith('/settings/');


    return (
        <div className={`app-shell-container ${isLoading ? 'is-loading' : ''}`}>
            <Navbar bg="light" variant="light" expand="lg" className="px-3 border-bottom app-shell-header">
                <Container fluid>
                    <Navbar.Brand as={Link} to={currentVault ? getVaultLink(currentVault.id) : '/'}>
                        <strong>{currentVault ? `${currentVault.name}` : 'Nexidion'}</strong>
                    </Navbar.Brand>
                    <Navbar.Toggle aria-controls="app-navbar-collapse" className="navbar-toggler-sm" />
                    <Navbar.Collapse id="app-navbar-collapse">
                        <Nav className="ms-auto align-items-center">
                            {/* --- Vault Switcher Dropdown --- */}
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
                                {/* KORREKTUR: Deaktivieren, wenn auf irgendeiner Settings-Seite */}
                                <NavDropdown.Item as={Link} to="/settings/vaults" disabled={isOnAnySettingsPage}>
                                    Vaults verwalten...
                                </NavDropdown.Item>
                            </NavDropdown>

                            {/* --- LLM Dropdown --- */}
                            <NavDropdown title={`LLM: ${chatModel?.name || '...'}`} id="llm-settings-dropdown" className="me-lg-2">
                                {/* KORREKTUR: Deaktivieren, wenn auf irgendeiner Settings-Seite */}
                                <NavDropdown.Item as={Link} to={llmSettingsPath} disabled={isOnAnySettingsPage}>
                                    Modelle verwalten...
                                </NavDropdown.Item>
                            </NavDropdown>

                            {/* --- User Dropdown --- */}
                            <NavDropdown title={user?.username || 'Account'} id="user-settings-dropdown" align="end" className="me-lg-2">
                                {/* KORREKTUR: Deaktivieren, wenn auf irgendeiner Settings-Seite */}
                                <NavDropdown.Item as={Link} to="/settings/user" disabled={isOnAnySettingsPage}>
                                    Benutzereinstellungen
                                </NavDropdown.Item>
                                <NavDropdown.Divider />
                                <NavDropdown.ItemText>
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
                <Outlet />
            </main>
        </div>
    );
}