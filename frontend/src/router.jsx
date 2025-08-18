import { createBrowserRouter } from 'react-router-dom';

// --- LAYOUTS & GLOBALE KOMPONENTEN ---
import { ProtectedRoute } from './layouts/ProtectedRoute.jsx';
// NEU: Importiere den Admin-Schutz
import AdminProtectedRoute from './layouts/AdminProtectedRoute.jsx';
import AppShell from './layouts/AppShell.jsx';
import ErrorPage from './components/ErrorPage.jsx';

// --- FEATURE-SEITEN ---
import LoginPage from './features/auth/LoginPage.jsx';
import WorkspaceLayout from './features/workspace/WorkspaceLayout.jsx';
import NodeContent from './features/nodes/NodeContent.jsx';
import VaultIndexRedirector from './features/vaults/VaultIndexRedirector.jsx';
import VaultManager from './features/settings/VaultManager.jsx';
import LlmSettings from './features/settings/LlmSettings.jsx';
import UserSettings from './features/settings/UserSettings.jsx';
import AdminDashboard from './features/admin/AdminDashboard.jsx';

const router = createBrowserRouter([
    // --- GRUPPE 1: Öffentliche Route ---
    {
        path: "/login",
        element: <LoginPage />,
    },

    // --- GRUPPE 2: Geschützte Routen ---
    {
        path: "/",
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
                        path: "vaults/:vaultId",
                        element: <WorkspaceLayout />,
                        children: [
                            {
                                path: "nodes/:nodeId",
                                element: <NodeContent />,
                            },
                        ]
                    },
                    // Alle Einstellungs-Seiten für normale Benutzer
                    {
                        path: "settings/vaults",
                        element: <VaultManager />,
                    },
                    {
                        path: "settings/llms",
                        element: <LlmSettings />,
                    },
                    {
                        path: "settings/user",
                        element: <UserSettings />,
                    },

                    // --- HIER IST DIE ÄNDERUNG ---
                    // Wir erstellen eine neue verschachtelte Gruppe,
                    // die von unserem AdminProtectedRoute bewacht wird.
                    {
                        element: <AdminProtectedRoute />,
                        children: [
                            {
                                path: "admin",
                                element: <AdminDashboard />,
                            },
                            // Hier könnten zukünftig weitere Admin-Seiten hinzukommen
                            // z.B. { path: "admin/stats", element: <AdminStats /> }
                        ]
                    },
                ]
            }
        ]
    },
]);

export default router;