import {createBrowserRouter} from 'react-router-dom';

// --- Grundlegende Layouts & Seiten ---
import AppShell from './layouts/AppShell.jsx';
import WorkspaceLayout from './layouts/WorkspaceLayout.jsx';
import ErrorPage from './features/app/ErrorPage.jsx';

// --- Feature: Authentifizierung ---
import LoginPage from './features/auth/LoginPage.jsx';
import {loginAction} from './features/auth/auth.action.js';
import {logoutAction} from './features/auth/auth.action.js';
import {protectedLoader} from './features/auth/auth.loader.js';

// --- Feature: Node-Verwaltung ---
import NodeContent from './features/nodes/NodeContent.jsx';
import {vaultTreeLoader, nodeContentLoader, nodeVersionsLoader} from './features/nodes/nodes.loader.js';
import {vaultIndexLoader} from './features/vaults/vaults.index.loader.js';
import {nodeAction} from './features/nodes/nodes.action.js';

// --- Feature: Vault-Verwaltung (NEU & AKTUALISIERT) ---
import VaultManager from './features/vaults/VaultManager.jsx'; // NEU: Importiert die volle Verwaltungsseite
import {vaultManagerLoader} from './features/vaults/vaults.manager.loader.js'; // NEU: Loader für die Vault-Liste
import {vaultManagerAction} from './features/vaults/vaults.manager.action.js'; // NEU: Action für Create, Rename, Delete, Activate

const VaultIndex = () => <div className="p-4 text-muted">Wählen Sie einen Knoten aus oder erstellen Sie einen
    neuen.</div>;

// --- Feature: Admin ---
import AdminDashboard from './features/admin/AdminDashboard.jsx';

// ===============================================================
// ROUTER-KONFIGURATION
// ===============================================================
const router = createBrowserRouter([
    // --- GRUPPE 1: Öffentliche Routen ---
    {
        path: "/login",
        element: <LoginPage/>,
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
        element: <AppShell/>,
        loader: protectedLoader,
        errorElement: <ErrorPage/>,
        children: [
            // --- A) Die Haupt-Arbeitsansicht ---
            {
                path: "vaults/:vaultId",
                element: <WorkspaceLayout/>,
                loader: vaultTreeLoader,
                // action: createVaultAction, // ENTFERNT: Die Action gehört zur Verwaltungsseite, nicht zum Layout.
                children: [
                    {
                        index: true,
                        element: <VaultIndex/>,
                        loader: vaultIndexLoader,
                    },
                    {
                        path: "nodes/:nodeId",
                        element: <NodeContent/>,
                        loader: nodeContentLoader,
                        action: nodeAction,
                        children: [
                            {
                                path: "versions",
                                loader: nodeVersionsLoader,
                            }
                        ]
                    },
                ]
            },

            // --- B) Die Vault-Verwaltungsseite (ersetzt die alte "welcome" Seite) ---
            // Diese Route ist der neue, zentrale Ort für alle Vault-Operationen.
            {
                path: "settings/vaults", // NEU: Eine logische URL für Einstellungen
                element: <VaultManager/>,
                loader: vaultManagerLoader, // Lädt die Liste aller Vaults
                action: vaultManagerAction,  // Verarbeitet alle Formulare auf der Seite
            },

            // --- C) Die Admin-Dashboard-Seite ---
            {
                path: "admin",
                element: <AdminDashboard/>,
                // loader: adminDataLoader,
            },

            // --- D) Eine "leere" Index-Route ---
            // Wird vom `protectedLoader` behandelt, der zum ersten Vault oder zur Erstellungsseite umleitet.
            {
                index: true,
            }
        ],
    },
]);

export default router;