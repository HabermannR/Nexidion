// src/features/auth/auth.loader.js
import { redirect } from 'react-router-dom';
import { checkAuth } from './auth.helpers.js'; // Wir importieren die Hilfsfunktion

// Dies ist der Loader, der Routen schützt.
export function protectedLoader() {
    const isAuthenticated = checkAuth();

    if (!isAuthenticated) {
        console.log("[Auth Loader] Nicht authentifiziert. Umleitung zu /login.");
        return redirect('/login');
    }

    console.log("[Auth Loader] Authentifiziert. Route wird geladen.");
    return null;
}