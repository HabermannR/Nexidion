// src/router.jsx
import { createBrowserRouter } from "react-router-dom";

// --- Layouts ---
// Die Haupt-Hülle für den geschützten Bereich der Anwendung.
import MainLayout from "./layouts/MainLayout.jsx";

// --- Feature: Authentifizierung ---
// Die Seite, auf der sich der Benutzer anmeldet.
import LoginPage from "./features/auth/LoginPage.jsx";
// Die Action, die den Login-Vorgang abwickelt.
import { loginAction } from "./features/auth/auth.action.js";
// Der Loader, der prüft, ob eine Route geschützt ist.
import { protectedLoader } from "./features/auth/auth.loader.js";

// --- Feature: Node-Verwaltung ---
// Der Loader, der den Baum und andere Node-Daten für eine Vault lädt.
import { vaultTreeLoader } from "./features/nodes/nodes.loader.js";
// Die Komponente, die den Inhalt eines Nodes anzeigt (Beispiel).
import NodeContent from "./features/nodes/NodeContent.jsx";
// Eine Platzhalter-Komponente, die angezeigt wird, wenn noch kein Node ausgewählt ist.
const VaultIndex = () => <div className="p-4 text-muted">Wählen Sie einen Knoten aus dem Baum auf der linken Seite.</div>;

// --- Fehlerbehandlung ---
// Eine einfache Fehlerseite, die angezeigt wird, wenn ein Loader fehlschlägt.
const ErrorPage = () => <div className="p-4 alert alert-danger">Ein Fehler ist aufgetreten. Bitte laden Sie die Seite neu.</div>

// --- Router-Konfiguration ---
const router = createBrowserRouter([
    // ===================================================================
    // GRUPPE 1: Öffentliche Routen (kein Auth-Schutz)
    // ===================================================================
    {
        path: "/login",
        element: <LoginPage />,
        action: loginAction, // Verknüpft das Formular in LoginPage mit der Login-Logik
    },

    // ===================================================================
    // GRUPPE 2: Geschützte Routen
    // ===================================================================
    {
        id: 'root', // Eine ID für die Route, nützlich für Hooks wie useRouteLoaderData
        path: "/",
        element: <MainLayout />,
        loader: protectedLoader, // WICHTIG: Dieser Loader schützt diese und ALLE Kind-Routen
        errorElement: <ErrorPage />, // Fallback-UI, wenn ein Loader fehlschlägt
        children: [
            {
                // Route für eine spezifische Vault.
                // Sie wird nur erreicht, wenn der protectedLoader "ok" sagt.
                path: "vaults/:vaultId",
                loader: vaultTreeLoader, // Lädt die Daten für den Baum, NACHDEM der Auth-Check bestanden wurde
                children: [
                    {
                        // Index-Route: Wird angezeigt, wenn die URL /vaults/:vaultId ist.
                        index: true,
                        element: <VaultIndex />
                    },
                    {
                        // Detail-Route: Wird angezeigt, wenn die URL /vaults/:vaultId/nodes/:nodeId ist.
                        path: "nodes/:nodeId",
                        element: <NodeContent />,
                        // Hier könnte ein weiterer Loader hin, der NUR den Inhalt für den spezifischen Node lädt.
                        // loader: nodeContentLoader,
                    }
                ]
            },
            {
                // Eine weitere geschützte Route, z.B. für die Einstellungen.
                path: "settings/vaults",
                // element: <VaultSettingsPage />, // Hier käme die Einstellungs-Komponente hin
            }
        ],
    },
]);

export default router;