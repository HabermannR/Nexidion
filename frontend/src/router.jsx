// router.jsx

import { createBrowserRouter } from 'react-router-dom';

// --- Grundlegende Layouts & Seiten ---
import AppShell from './layouts/AppShell.jsx';
import WorkspaceLayout from './features/workspace/WorkspaceLayout.jsx';
import ErrorPage from './components/ErrorPage.jsx';

// --- Feature: Authentifizierung ---
import LoginPage from './features/auth/LoginPage.jsx';
import { loginAction } from './features/auth/auth.action.js';
import { logoutAction } from './features/auth/auth.action.js';
import { protectedLoader } from './features/auth/auth.loader.js';

// --- Feature: Node-Verwaltung ---
import NodeContent from './features/workspace/center-panel/NodeContent.jsx';

import { vaultIndexLoader } from './features/vaults/vaults.index.loader.js';
import VaultIndexRedirector from './features/vaults/VaultIndexRedirector.jsx';
import VaultManager from './features/settings/VaultManager.jsx'; // Component remains
import AdminDashboard from './features/admin/AdminDashboard.jsx';

// --- NEUE SETTINGS-SEITEN ---
import LlmSettings from './features/settings/LlmSettings.jsx';
import UserSettings from './features/settings/UserSettings.jsx';


// --- VERALTETE IMPORTS (nicht mehr benötigt nach dem Refactoring) ---
// import { vaultManagerLoader } from './features/vaults/vaults.manager.loader.js';
// import { vaultManagerAction } from './features/vaults/vaults.manager.action.js';


const router = createBrowserRouter([
    // --- GRUPPE 1: Öffentliche Routen ---
    {
        path: "/login",
        element: <LoginPage />,
        action: loginAction,
    },
    {
        path: "/logout",
        action: logoutAction,
    },

    // --- GRUPPE 2: Geschützte Routen (alles, was einen Login erfordert) ---
    {
        id: 'root',
        path: "/",
        element: <AppShell />,
        loader: protectedLoader,
        errorElement: <ErrorPage />,
        shouldRevalidate: ({ currentUrl, nextUrl }) => {
            return currentUrl.pathname !== nextUrl.pathname;
        },
        children: [
            {
                path: "vaults/:vaultId",
                id: 'workspace-layout',
                element: <WorkspaceLayout />,
                children: [
                    {
                        index: true,
                        loader: vaultIndexLoader,
                        element: <VaultIndexRedirector />,
                    },
                    {
                        path: "nodes/:nodeId",
                        id: 'node-detail',
                        element: <NodeContent />,
                    },
                ]
            },

            // --- A) Die Vault-Verwaltungsseite (REFACTORING) ---
            // Loader und Action wurden entfernt. Die Komponente nutzt jetzt TanStack Query.
            {
                path: "settings/vaults",
                element: <VaultManager />,
            },

            // --- B) NEUE EINSTELLUNGS-SEITEN ---
            {
                path: "settings/llms",
                element: <LlmSettings />,
            },
            {
                path: "settings/user",
                element: <UserSettings />,
            },

            // --- C) Die Admin-Dashboard-Seite (unverändert) ---
            {
                path: "admin",
                element: <AdminDashboard />,
            },

            // --- D) Eine "leere" Index-Route für die App-Wurzel (unverändert) ---
            {
                index: true,
                // Hier könnte man z.B. eine Willkommens-Seite oder eine Umleitung
                // zum zuletzt besuchten Vault einbauen.
            }
        ],
    },
]);

export default router;