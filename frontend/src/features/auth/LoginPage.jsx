// src/features/auth/LoginPage.jsx (Die neue V4-Version)
import React from 'react';
import { useLoginMutation } from './useLoginMutation';
import './LoginPage.css';

export default function LoginPage() {
    const { mutate: login, isPending, error } = useLoginMutation();

    const handleSubmit = (event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const credentials = Object.fromEntries(formData);
        login(credentials);
    };

    return (
        <div className="d-flex align-items-center justify-content-center vh-100 bg-light">
            <div className="card shadow-lg p-4 login-card">
                <div className="card-body">
                    <h2 className="card-title text-center mb-4">Nexidion v4</h2>
                    <form onSubmit={handleSubmit}>
                        <div className="mb-3">
                            <label htmlFor="username" className="form-label">Username</label>
                            <input id="username" name="username" type="text" placeholder="z.B. admin" required className="form-control form-control-lg" autoComplete="username" disabled={isPending}/>
                        </div>
                        <div className="mb-3">
                            <label htmlFor="password" className="form-label">Password</label>
                            <input id="password" name="password" type="password" placeholder="Passwort eingeben" required className="form-control form-control-lg" autoComplete="current-password" disabled={isPending}/>
                        </div>

                        {error && (
                            <div className="alert alert-danger mt-3" role="alert">
                                {error.response?.status === 401
                                    ? 'Benutzername oder Passwort ist falsch.'
                                    : 'Ein unerwarteter Fehler ist aufgetreten.'}
                            </div>
                        )}

                        <button type="submit" className="btn btn-primary w-100 mt-4 py-2" disabled={isPending}>
                            {isPending ? 'Entsperren...' : 'Unlock'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}