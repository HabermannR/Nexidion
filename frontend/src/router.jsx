import { createBrowserRouter } from 'react-router-dom';

import { ProtectedRoute } from './layouts/ProtectedRoute.jsx';
import AdminProtectedRoute from './layouts/AdminProtectedRoute.jsx';
import AppShell from './layouts/AppShell.jsx';
import ErrorPage from './components/ErrorPage.jsx';

import LoginPage from './features/auth/LoginPage.jsx';
import WorkspaceLayout from './features/workspace/WorkspaceLayout.jsx';
import NodeContent from './features/nodes/NodeContent.jsx';
import VaultIndexRedirector from './features/vaults/VaultIndexRedirector.jsx';
import VaultManager from './features/settings/VaultManager.jsx';
import UserSettings from './features/settings/UserSettings.jsx';
import AdminDashboard from './features/admin/AdminDashboard.jsx';

const router = createBrowserRouter([
    {
        path: '/login',
        element: <LoginPage />,
    },
    {
        path: '/',
        element: <ProtectedRoute />,
        errorElement: <ErrorPage />,
        children: [
            {
                element: <AppShell />,
                children: [
                    {
                        index: true,
                        element: <VaultIndexRedirector />,
                    },
                    {
                        path: 'vaults/:vaultId',
                        element: <WorkspaceLayout />,
                        children: [
                            {
                                path: 'nodes/:nodeId',
                                element: <NodeContent />,
                            },
                        ],
                    },
                    {
                        path: 'settings/vaults',
                        element: <VaultManager />,
                    },
                    {
                        path: 'settings/user',
                        element: <UserSettings />,
                    },
                    {
                        element: <AdminProtectedRoute />,
                        children: [
                            {
                                path: 'admin',
                                element: <AdminDashboard />,
                            },
                        ],
                    },
                ],
            },
        ],
    },
]);

export default router;
