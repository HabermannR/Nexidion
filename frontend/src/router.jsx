import { createBrowserRouter } from 'react-router-dom';

// --- LAYOUTS & GLOBALE KOMPONENTEN ---
// V4: Der neue "Türsteher" für geschützte Bereiche.
import { ProtectedRoute } from './layouts/ProtectedRoute.jsx';
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

// Die alten V3-Imports für 'action' und 'loader' sind nicht mehr notwendig und wurden entfernt.

const router = createBrowserRouter([
    // --- GRUPPE 1: Öffentliche Route (kein Login erforderlich) ---
    // V4: Die Login-Seite hat keine 'action' mehr. Die Logik steckt im 'useLoginMutation'-Hook.
    {
        path: "/login",
        element: <LoginPage />,
    },

    // --- GRUPPE 2: Geschützte Routen (alles, was einen Login erfordert) ---
    // V4: Der "root"-Pfad wird nun von unserer 'ProtectedRoute'-Komponente bewacht.
    // Es gibt keinen 'loader' oder 'shouldRevalidate' mehr.
    {
        path: "/",
        element: <ProtectedRoute />,
        errorElement: <ErrorPage />,
        children: [
            // Wenn der Zugang durch 'ProtectedRoute' gewährt wurde, wird das AppShell-Layout gerendert.
            // Alle folgenden Routen leben innerhalb dieses Layouts.
            {
                element: <AppShell />,
                children: [
                    // Wenn der Pfad genau "/" ist, entscheidet der 'VaultIndexRedirector', wohin es geht.
                    {
                        index: true,
                        element: <VaultIndexRedirector />,
                    },
                    // Die Haupt-Workspace-Route
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
                    // Alle Einstellungs- und Admin-Seiten
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
                    {
                        path: "admin",
                        element: <AdminDashboard />,
                    },
                ]
            }
        ]
    },

    // Die Route "/logout" wurde entfernt. Der Logout-Prozess wird durch den
    // 'useLogoutMutation'-Hook gesteuert, der in der 'AppShell' aufgerufen wird.
]);

export default router;