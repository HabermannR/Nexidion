// src/App.jsx

import React from 'react';
import { RouterProvider } from 'react-router-dom';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import router from './router';
import AppLoading from './components/AppLoading'; // Importiere die Ladekomponente

function App() {
    return (
        <DndProvider backend={HTML5Backend}>
            <RouterProvider
                router={router}
                fallbackElement={<AppLoading />}
            />
        </DndProvider>
    );
}

export default App;