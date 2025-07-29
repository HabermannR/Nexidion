// src/main.jsx

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import 'boxicons/css/boxicons.min.css';
import './index.css';

// Erstelle die Root-Instanz EINMAL außerhalb der Render-Funktion.
const rootElement = document.getElementById('root');
const root = ReactDOM.createRoot(rootElement);

// Rendere die App in die erstellte Root.
// Wir kommentieren StrictMode für den Test aus.
root.render(
    // <React.StrictMode>
    <App />
    // </React.StrictMode>
);