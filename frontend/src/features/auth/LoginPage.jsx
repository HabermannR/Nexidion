// src/features/auth/LoginPage.jsx

import React from 'react';
// NEU: Importiere <Form> und useActionData von React Router
import { Form, useActionData } from 'react-router-dom';
import './LoginPage.css'; // Unser neues, sauberes CSS

export default function LoginPage() {
    // NEU: useActionData holt sich Fehlerdaten, die von der Action zurückgegeben werden.
    const actionData = useActionData();

    return (
        <div className="d-flex align-items-center justify-content-center vh-100 bg-light">
            <div className="card shadow-lg p-4 login-card">
                <div className="card-body">
                    <h2 className="card-title text-center mb-4">Nexidion v4</h2>

                    {/* NEU: Wir benutzen die <Form>-Komponente von React Router.
              Sie ruft automatisch die verknüpfte 'action' auf. */}
                    <Form method="post">
                        <div className="mb-3">
                            <label htmlFor="username" className="form-label">Username</label>
                            <input
                                id="username"
                                name="username" // WICHTIG: name-Attribut für Form-Daten
                                type="text"
                                placeholder="z.B. admin"
                                required
                                className="form-control form-control-lg"
                                autoComplete="username"
                            />
                        </div>
                        <div className="mb-3">
                            <label htmlFor="password" className="form-label">Password</label>
                            <input
                                id="password"
                                name="password" // WICHTIG: name-Attribut für Form-Daten
                                type="password"
                                placeholder="Passwort eingeben"
                                required
                                className="form-control form-control-lg"
                                autoComplete="current-password"
                            />
                        </div>

                        {/* Zeigt Fehler an, die von der Action zurückgegeben wurden */}
                        {actionData?.error && (
                            <div className="alert alert-danger mt-3" role="alert">
                                {actionData.error}
                            </div>
                        )}

                        <button type="submit" className="btn btn-primary w-100 mt-4 py-2">
                            Unlock
                        </button>
                    </Form>
                </div>
            </div>
        </div>
    );
}