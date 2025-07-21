import React, { useEffect } from 'react';
import {
    createBrowserRouter,
    RouterProvider,
    Route,
    createRoutesFromElements,
    Outlet,
    ScrollRestoration,
    useLoaderData // NEU: Um Daten vom Loader abzurufen
} from 'react-router-dom';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';

// Provider und Komponenten
import { AuthProvider } from './context/AuthContext';
import { AppProvider, useAppContext } from './context/AppContext'; // useAppContext importieren
import TopBar from './components/layout/TopBar';
import Login from './components/Login';
import NodesView from './pages/NodesView';
import NodeList from './pages/NodeList';
import VaultSettings from './pages/settings/VaultSettings';
import ProtectedRoute from './ProtectedRoute';
import api from './api/axios'; // NEU: API-Instanz für den Loader

// Globale Stile
import './App.css';

// ========================================================================
// NEU: Der Daten-Loader für den Vault-Baum
// Diese Funktion wird von React Router ausgeführt, BEVOR die Komponente rendert.
// ========================================================================
export async function vaultTreeLoader({ params }) {
    const { vaultId } = params;
    console.log(`[Loader] Lade Tree für Vault-ID: ${vaultId}`);
    try {
        const response = await api.get(`/api/vaults/${vaultId}/nodes?format=tree`);
        // Wir geben die Daten direkt zurück. React Router macht sie verfügbar.
        return response.data;
    } catch (error) {
        console.error("Fehler beim Laden des Projektbaums im Loader:", error);
        // Bei einem Fehler (z.B. Vault nicht gefunden) wird ein Fehler geworfen.
        // Diesen kann man mit einem `errorElement` in der Route abfangen.
        throw new Response("Vault nicht gefunden", { status: 404 });
    }
}

// ========================================================================
// NEU: Eine Layout-Komponente für den Vault-Bereich
// Ihre Aufgabe ist es, die geladenen Daten in den globalen Context zu legen.
// ========================================================================
function VaultLayout() {
    // Holt die Daten, die der `vaultTreeLoader` zurückgegeben hat.
    const treeDataFromLoader = useLoaderData();
    const { setTreeDataForContext } = useAppContext();

    // Effekt, um die geladenen Daten in den globalen AppContext zu schreiben.
    useEffect(() => {
        if (treeDataFromLoader) {
            console.log("[VaultLayout] Setze Tree-Daten aus dem Loader in den Context.");
            setTreeDataForContext(treeDataFromLoader);
        }
    }, [treeDataFromLoader, setTreeDataForContext]);

    // Rendert die eigentliche Kind-Route (entweder NodeList oder NodesView)
    return <Outlet />;
}

function AppLayout() {
    return (
        <div className="app-container">
            <TopBar />
            <ScrollRestoration />
            <main>
                <Outlet />
            </main>
        </div>
    );
}

// Router mit der neuen, architektonisch sauberen Struktur
const router = createBrowserRouter(
    createRoutesFromElements(
        <>
            {/* GRUPPE 1: Öffentliche Routen */}
            <Route path="/" element={<Login />} />

            {/* GRUPPE 2: Geschützte Routen */}
            <Route
                element={
                    <ProtectedRoute>
                        <AppLayout />
                    </ProtectedRoute>
                }
            >
                <Route path="/settings/vaults" element={<VaultSettings />} />

                {/* --- GRUPPE FÜR VAULT-SPEZIFISCHE SEITEN (ÜBERARBEITET) --- */}
                <Route
                    path="/vaults/:vaultId"
                    loader={vaultTreeLoader}  // 1. Loader wird hier angehängt
                    element={<VaultLayout />}   // 2. Layout-Komponente verarbeitet die Daten
                    // Optional: errorElement={<VaultErrorPage />}
                >
                    {/* Die Index-Route leitet weiterhin weiter, nutzt aber jetzt die Daten aus dem Context */}
                    <Route index element={<NodeList />} />

                    {/* Die Detail-Route rendert die Node-Ansicht */}
                    <Route path="nodes/:nodeId" element={<NodesView />} />
                </Route>
            </Route>
        </>
    )
);

function App() {
    return (
        <AuthProvider>
            <AppProvider>
                <DndProvider backend={HTML5Backend}>
                    <RouterProvider router={router} />
                </DndProvider>
            </AppProvider>
        </AuthProvider>
    );
}

export default App;