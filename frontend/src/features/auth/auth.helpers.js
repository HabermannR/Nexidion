// src/features/auth/auth.helpers.js

// Diese Funktion prüft, ob ein Authentifizierungs-Token vorhanden ist.
// Sie kann von überall im Auth-Feature importiert und genutzt werden.
export const checkAuth = () => {
    const token = localStorage.getItem('authToken');
    return !!token;
};

// Hier könnten weitere Hilfsfunktionen stehen, z.B.:
export const logoutUser = () => {
    localStorage.removeItem('authToken');
    // vielleicht auch redirect, wenn es außerhalb des Routers genutzt wird
};

export const getToken = () => {
    return localStorage.getItem('authToken');
};