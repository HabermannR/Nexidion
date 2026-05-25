// src/layouts/AppShell.jsx
import React, { useEffect } from 'react';
import { Link, useLocation, useParams, Outlet } from 'react-router-dom';
import { Navbar, Nav, Button, NavDropdown, Container } from 'react-bootstrap';

import { useLogoutMutation } from '../features/auth/useLogoutMutation.js';
import { useWorkspaceStore } from '../features/workspace/workspaceStore';
import 'bootstrap/dist/css/bootstrap.min.css';
import './AppShell.css';

import { useUserQuery } from '../features/auth/useUserQuery';
import { useVaultsQuery } from '../features/vaults/hooks/useVaultsQuery';
import PrintPreview from "../features/print/PrintPreview.jsx";

export default function AppShell() {
    const { data: vaults, isLoading: isLoadingVaults } = useVaultsQuery();
    const { data: user, isLoading: isLoadingUser } = useUserQuery();
    const { mutate: logout } = useLogoutMutation();
    const { vaultId, nodeId } = useParams();
    const location = useLocation();

    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);
    const setLastValidPathForVault = useWorkspaceStore(state => state.setLastValidPathForVault);
    const setLastActiveVaultId = useWorkspaceStore(state => state.setLastActiveVaultId);

    const isLoading = isLoadingVaults || isLoadingUser;
    const currentVault = vaults?.find(v => v.id.toString() === vaultId);

    useEffect(() => {
        if (vaultId && nodeId) {
            setLastValidPathForVault(vaultId, location.pathname);
        }
    }, [vaultId, nodeId, location.pathname, setLastValidPathForVault]);

    useEffect(() => {
        if (vaultId) {
            setLastActiveVaultId(vaultId);
        }
    }, [vaultId, setLastActiveVaultId]);

    const getVaultLink = (targetVaultId) => {
        return lastValidPaths[targetVaultId] || `/vaults/${targetVaultId}`;
    };

    const isOnAnySettingsPage = location.pathname.startsWith('/settings/');
    const isOnAdminPage = location.pathname.startsWith('/admin');

return (
        <div className={`app-shell-container ${isLoading ? 'is-loading' : ''}`}>
            <Navbar bg="light" variant="light" expand="lg" className="px-3 border-bottom app-shell-header">
                <Container fluid>
                    <Navbar.Brand as={Link} to={currentVault ? getVaultLink(currentVault.id) : '/'}>
                        <strong>{currentVault ? currentVault.name : 'Nexidion'}</strong>
                    </Navbar.Brand>
                    <Navbar.Toggle aria-controls="app-navbar-collapse" className="navbar-toggler-sm" />
                    <Navbar.Collapse id="app-navbar-collapse">
                        <Nav className="ms-auto align-items-center">

                            {/* Vault Switcher */}
                            <NavDropdown title="Switch Vault" id="vault-switcher-dropdown" className="me-lg-3">
                                <div className="scrollable-dropdown">
                                    {isLoadingVaults ? (
                                        <NavDropdown.Item disabled>...</NavDropdown.Item>
                                    ) : (
                                        vaults?.map(vault => (
                                            <NavDropdown.Item
                                                key={vault.id}
                                                as={Link}
                                                to={getVaultLink(vault.id)}
                                                active={vault.id.toString() === vaultId}
                                            >
                                                {vault.name}
                                            </NavDropdown.Item>
                                        ))
                                    )}
                                </div>
                                <NavDropdown.Divider />
                                {!user?.is_guest && (
                                    <NavDropdown.Item as={Link} to="/settings/vaults" disabled={isOnAnySettingsPage}>
                                        Manage Vaults...
                                    </NavDropdown.Item>
                                )}
                            </NavDropdown>

                            {/* Admin link */}
                            {user?.is_admin && (
                                <Nav.Link
                                    as={Link}
                                    to="/admin"
                                    className="me-lg-3"
                                    active={isOnAdminPage}
                                >
                                    Admin
                                </Nav.Link>
                            )}

                            {/* User dropdown */}
                            <NavDropdown title={user?.username || 'Account'} id="user-settings-dropdown" align="end" className="me-lg-2">
                                <NavDropdown.Item as={Link} to="/settings/user" disabled={isOnAnySettingsPage}>
                                    User Settings
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
            <PrintPreview />
        </div>
    );
}
