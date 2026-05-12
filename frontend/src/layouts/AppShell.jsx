// src/layouts/AppShell.jsx
import React, { useEffect, useRef } from 'react';
import { Link, useLocation, useParams, Outlet } from 'react-router-dom';
import { Navbar, Nav, Button, NavDropdown, Container } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';

import { useLogoutMutation } from '../features/auth/useLogoutMutation.js';
import { useWorkspaceStore } from '../features/workspace/workspaceStore';
import apiClient from '../api/apiClient';
import 'bootstrap/dist/css/bootstrap.min.css';
import './AppShell.css';

// 1. IMPORTIERE DEINEN SHARED HOOK HIER:
import { useUserQuery } from '../features/auth/useUserQuery';

const useVaultsQuery = () => {
    const etagRef = useRef(null);
    return useQuery({
        queryKey: ['allVaults'],
        queryFn: async () => {
            const headers = {};
            if (etagRef.current) {
                headers['If-None-Match'] = etagRef.current;
            }
            const res = await apiClient.get('/api/vaults/', { headers, validateStatus: s => s < 500 });
            if (res.status === 304) {
                // Return undefined so TanStack Query keeps previous data
                return undefined;
            }
            const etag = res.headers['etag'];
            if (etag) etagRef.current = etag;
            return res.data;
        },
        // Keep previous data on 304
        placeholderData: (prev) => prev,
    });
};

export default function AppShell() {
    const { data: vaults, isLoading: isLoadingVaults } = useVaultsQuery();
    const { data: user, isLoading: isLoadingUser } = useUserQuery();
    const { mutate: logout } = useLogoutMutation();
    const { vaultId, nodeId } = useParams();
    const location = useLocation();

    const lastValidPaths = useWorkspaceStore(state => state.lastValidPaths);
    const setLastValidPathForVault = useWorkspaceStore(state => state.setLastValidPathForVault);

    const isLoading = isLoadingVaults || isLoadingUser;
    const currentVault = vaults?.find(v => v.id.toString() === vaultId);

    useEffect(() => {
        if (vaultId && nodeId) {
            setLastValidPathForVault(vaultId, location.pathname);
        }
    }, [vaultId, nodeId, location.pathname, setLastValidPathForVault]);

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
                            <NavDropdown title="Vault wechseln" id="vault-switcher-dropdown" className="me-lg-3">
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
                                <NavDropdown.Item as={Link} to="/settings/vaults" disabled={isOnAnySettingsPage}>
                                    Vaults verwalten...
                                </NavDropdown.Item>
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
