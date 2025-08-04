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
// --- AKTUALISIERT: Wir importieren nur noch die benötigten Loader ---
import { vaultTreeLoader, nodeDetailLoader } from './features/workspace/nodes.loader.js';
import { nodeAction } from './features/workspace/nodes.action.js';

// --- Unveränderte Imports für andere App-Teile ---
import { vaultIndexLoader } from './features/vaults/vaults.index.loader.js';
import VaultIndexRedirector from './features/vaults/VaultIndexRedirector.jsx';
import VaultManager from './features/vaults/VaultManager.jsx';
import { vaultManagerLoader } from './features/vaults/vaults.manager.loader.js';
import { vaultManagerAction } from './features/vaults/vaults.manager.action.js';
import AdminDashboard from './features/admin/AdminDashboard.jsx';

// ===============================================================
// ROUTER-KONFIGURATION (NEU & VEREINFACHT)
// ===============================================================
const router = createBrowserRouter([
    // --- GRUPPE 1: Öffentliche Routen (unverändert) ---
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
        // +++ DIES IST DIE EINZIGE ÄNDERUNG +++
        // Ersetze die alte shouldRevalidate-Funktion durch diese.
        // Sie ist einfacher, robuster und löst dein Problem.
        shouldRevalidate: ({ currentUrl, nextUrl }) => {
            // Revalidiere immer, wenn sich der Pfad ändert.
            // Ignoriere Änderungen, die nur Search-Parameter betreffen (z.B. ?version=...).
            return currentUrl.pathname !== nextUrl.pathname;
        },
        children: [
            {
                path: "vaults/:vaultId",
                id: 'workspace-layout',
                element: <WorkspaceLayout />,
                loader: vaultTreeLoader,
                // +++ KORRIGIERTE LOGIK +++
                shouldRevalidate: ({ currentParams, nextParams, formMethod }) => {
                    // Revalidiere, wenn die Vault-ID sich ändert (Navigation)
                    if (currentParams.vaultId !== nextParams.vaultId) {
                        return true;
                    }
                    // ODER wenn eine schreibende Aktion (POST, PUT, DELETE, etc.) stattgefunden hat
                    if (formMethod && formMethod.toLowerCase() !== 'get') {
                        return true;
                    }
                    // In allen anderen Fällen nicht revalidieren
                    return false;
                },
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
                        loader: nodeDetailLoader,
                        action: nodeAction,
                        // +++ KORRIGIERTE LOGIK +++
                        shouldRevalidate: ({ currentParams, nextParams, formMethod }) => {
                            // Revalidiere, wenn sich die Parameter ändern (Navigation)
                            if (currentParams.nodeId !== nextParams.nodeId ||
                                currentParams.vaultId !== nextParams.vaultId) {
                                return true;
                            }
                            // ODER wenn eine schreibende Aktion stattgefunden hat
                            if (formMethod && formMethod.toLowerCase() !== 'get') {
                                return true;
                            }
                            // In allen anderen Fällen nicht revalidieren
                            return false;
                        },
                    },
                ]
            },

            // --- B) Die Vault-Verwaltungsseite (unverändert) ---
            {
                path: "settings/vaults",
                element: <VaultManager />,
                loader: vaultManagerLoader,
                action: vaultManagerAction,
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