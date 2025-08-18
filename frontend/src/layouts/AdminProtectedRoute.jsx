import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { Spinner } from 'react-bootstrap';
import { useUserQuery } from '../features/auth/useUserQuery'; // Pfad zu deinem Hook

export default function AdminProtectedRoute() {
    // 1. Hole den Benutzerstatus mit dem zentralen Hook.
    // TanStack Query kümmert sich um das Caching.
    const { data: user, isLoading, isError } = useUserQuery();

    // 2. Zustand: Daten werden noch geladen.
    // Zeige einen Ladeindikator, anstatt die Seite unvollständig zu rendern.
    if (isLoading) {
        return (
            <div className="d-flex justify-content-center align-items-center" style={{ height: '80vh' }}>
                <Spinner animation="border" role="status">
                    <span className="visually-hidden">Loading...</span>
                </Spinner>
            </div>
        );
    }

    // 3. Zustand: Fehler beim Laden oder kein Benutzerobjekt vorhanden.
    // Dies passiert meist bei einem ungültigen/abgelaufenen Token.
    // Leite sicherheitshalber zum Login um.
    if (isError || !user) {
        return <Navigate to="/login" replace />;
    }

    // 4. Zustand: Benutzer ist eingeloggt, aber KEIN Admin.
    // Leite ihn zur Startseite oder einer "Kein Zugriff"-Seite um.
    if (!user.is_admin) {
        return <Navigate to="/" replace />;
    }

    // 5. Erfolgsfall: Der Benutzer ist Admin.
    // Rendere die verschachtelte Route (in unserem Fall das AdminDashboard).
    return <Outlet />;
}