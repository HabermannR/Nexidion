import React from 'react';
import { createBrowserRouter, RouterProvider, Route, createRoutesFromElements, Outlet, ScrollRestoration } from 'react-router-dom';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext'; // CORRECTED: Import from the 'context' folder
import TopBar from './components/TopBar';
import Login from './components/Login';
import NodeEdit from './components/NodeEdit';
import SearchResults from './components/SearchResults';
import './App.css';

// The Root component provides the consistent layout with the TopBar. It's perfect.
function Root() {
  return (
    <div className="app-container">
      <TopBar />
      <ScrollRestoration />
      <Outlet /> {/* Renders the matched child route */}
    </div>
  );
}

// UPDATED: The routes are simplified to reflect the new application flow.
const router = createBrowserRouter(
  createRoutesFromElements(
    <Route element={<Root />}>
      <Route path="/" element={<Login />} />
      
      {/* 
        The NodeEdit component is now the main hub of the application.
        It handles both the "no node selected" state and the "node selected" state.
      */}
      <Route path="/nodes" element={<NodeEdit />} />
      <Route path="/nodes/:nodeId" element={<NodeEdit />} />
     

    </Route>
  )
);

function App() {
  return (
    // We wrap all providers here. The order of AppProvider and DndProvider isn't critical,
    // but placing AppProvider here makes its context available to all routes.
    <AuthProvider>
      <AppProvider> {/* <<< THIS IS THE KEY ADDITION */}
        <DndProvider backend={HTML5Backend}>
          <RouterProvider router={router} />
        </DndProvider>
      </AppProvider>
    </AuthProvider>
  );
}

export default App;