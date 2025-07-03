import React from 'react';
import { createBrowserRouter, RouterProvider, Route, createRoutesFromElements, Outlet, ScrollRestoration } from 'react-router-dom';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
// Provider und Komponenten
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';
import TopBar from './components/layout/TopBar';
import Login from './components/Login';
import NodesView from './pages/NodesView'; 
import NodeList from './pages/NodeList'; 
import IFSLandkarteSVGExport from './components/special_nodes/IFSLandkarteSVGExport';
import ProtectedRoute from './ProtectedRoute';
// Globale Stile
import './App.css';

function Root() {
  return (
    <div className="app-container">
      <TopBar />
      <ScrollRestoration />
      <main className="flex-grow-1" style={{ minHeight: 0 }}>
         <Outlet />
      </main>
    </div>
  );
}

// Router mit geschützten Routen
const router = createBrowserRouter(
  createRoutesFromElements(
    <Route element={<Root />}>
      {/* Öffentliche Route - Login */}
      <Route path="/" element={<Login />} />
      
      {/* Geschützte Routen */}
      <Route path="/nodes" element={
        <ProtectedRoute>
          <NodeList />
        </ProtectedRoute>
      } /> 
      
      <Route path="/nodes/:nodeId" element={
        <ProtectedRoute>
          <NodesView />
        </ProtectedRoute>
      } />
      
      {/* SVG Export Route - jetzt auch geschützt */}
      <Route path="/exportSVG" element={
        <ProtectedRoute>
          <IFSLandkarteSVGExport />
        </ProtectedRoute>
      } />
    </Route>
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