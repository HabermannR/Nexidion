import { createBrowserRouter } from 'react-router-dom';

// --- Grundlegende Layouts & Seiten ---
import AppShell from './layouts/AppShell.jsx';
import WorkspaceLayout from './layouts/WorkspaceLayout.jsx';
import ErrorPage from './features/app/ErrorPage.jsx';

// --- Feature: Authentifizierung ---
import LoginPage from './features/auth/LoginPage.jsx';
import { loginAction } from './features/auth/auth.action.js';
import { logoutAction } from './features/auth/auth.action.js';
import { protectedLoader } from './features/auth/auth.loader.js';

// --- Feature: Node-Verwaltung ---
import NodeContent from './features/nodes/NodeContent.jsx';
import { vaultTreeLoader, nodeContentLoader, nodeVersionsLoader } from './features/nodes/nodes.loader.js';
import { vaultIndexLoader } from './features/vaults/vaults.loader.js'; // NEUER IMPORT
import { nodeAction } from './features/nodes/nodes.action.js';
const VaultIndex = () => <div className="p-4 text-muted">Wählen Sie einen Knoten aus oder erstellen Sie einen neuen.</div>;

// --- NEUE SEITEN ---
import AdminDashboard from './features/admin/AdminDashboard.jsx';
import VaultCreationPage from './features/vaults/VaultCreationPage.jsx';
import { createVaultAction } from './features/vaults/vaults.action.js';

// ===============================================================
// ROUTER-KONFIGURATION
// ===============================================================
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
        element: <AppShell />,        // DIE IMMER PRÄSENTE HÜLLE (Navbar etc.)
        loader: protectedLoader,      // Der "Wächter" für alle Kind-Routen
        errorElement: <ErrorPage />,  // Fallback, wenn irgendetwas schief geht
        children: [

            // --- A) Die Haupt-Arbeitsansicht ---
            {
                path: "vaults/:vaultId",
                element: <WorkspaceLayout />,
                loader: vaultTreeLoader, // <-- VERWENDET DEN VEREINFACHTEN LOADER
                action: createVaultAction, // <-- Behalte die Action hier
                children: [
                    {
                        index: true,
                        element: <VaultIndex />,
                        loader: vaultIndexLoader, // <-- DER INDEX BEKOMMT SEINEN EIGENEN LOADER
                    },
                    {
                        path: "nodes/:nodeId",
                        element: <NodeContent />,
                        loader: nodeContentLoader,
                        action: nodeAction,
                        children: [ // <-- NEU: VERSCHACHTELTE RESSOURCEN-ROUTE
                            {
                                // Diese Route rendert keine UI, sie existiert nur, damit wir ihren Loader ansprechen können.
                                path: "versions",
                                loader: nodeVersionsLoader,
                            }
                        ]
                    },
                ]
            },

            // --- B) Die Vault-Erstellungs-Seite ---
            // Hat kein spezielles Unter-Layout, wird direkt in der AppShell angezeigt.
            {
                path: "welcome/create-vault",
                element: <VaultCreationPage />,
                action: createVaultAction,
            },

            // --- C) Die Admin-Dashboard-Seite ---
            // Könnte ihr eigenes Admin-Layout haben, wenn nötig.
            // Hier wird sie einfach direkt in der AppShell gerendert.
            {
                path: "admin",
                element: <AdminDashboard />,
                // loader: adminDataLoader, // Ein Loader, der prüft, ob der User Admin ist.
            },

            // --- D) Eine "leere" Index-Route ---
            // Was passiert, wenn der User nur "/" aufruft?
            // Hier könnten wir z.B. zum ersten verfügbaren Vault umleiten.
            // Dies ist Aufgabe des `protectedLoader`.
            {
                index: true,
                // Kein Element, da der `protectedLoader` umleiten wird.
            }
        ],
    },
]);

export default router;