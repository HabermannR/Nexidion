// src/main.jsx (DEINE NEUE, ANGEPASSTE VERSION)

import React from 'react';
import ReactDOM from 'react-dom/client';

// 1. NEUE IMPORTS FÜR TANSTACK QUERY
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

import App from './App.jsx';
import { ToastProvider } from './components/ToastProvider.jsx';
import 'boxicons/css/boxicons.min.css';
import './index.css';

// 2. ERSTELLE EINE GLOBALE CLIENT-INSTANZ
// Diese Instanz ist das "Gehirn" von TanStack Query. Sie verwaltet den Cache.
// Wir erstellen sie außerhalb der Komponente, damit sie nicht bei jedem Re-Render neu erzeugt wird.
const queryClient = new QueryClient();


// Deine bestehende Logik zum Erstellen des Roots bleibt unverändert.
const rootElement = document.getElementById('root');
const root = ReactDOM.createRoot(rootElement);


// Rendere die App in die erstellte Root.
root.render(
    <React.StrictMode>
        <QueryClientProvider client={queryClient}>
            <ToastProvider>
                <App />
            </ToastProvider>
            <ReactQueryDevtools initialIsOpen={false} />
        </QueryClientProvider>
    </React.StrictMode>
);