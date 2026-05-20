// src/features/auth/LoginPage.jsx
import React from 'react';
import { useLoginMutation } from './useLoginMutation';
import { useGuestLoginMutation } from './useGuestLoginMutation';
import { useSystemConfigQuery } from './useSystemConfigQuery';
import './LoginPage.css';

export default function LoginPage() {
    const { mutate: login, isPending, error } = useLoginMutation();
    const { mutate: guestLogin, isPending: isGuestPending, error: guestError } = useGuestLoginMutation();
    const { data: systemConfig } = useSystemConfigQuery();

    const demoEnabled = systemConfig?.demo_mode_enabled === true;
    const anyPending = isPending || isGuestPending;

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

                    {/* ── Demo banner (shown only when demo mode is on) ── */}
                    {demoEnabled && (
                        <div
                            className="mb-4 p-3 rounded-3 border"
                            style={{
                                background: 'linear-gradient(135deg, #eef4ff 0%, #f0f9ff 100%)',
                                borderColor: '#b6d0f7 !important',
                            }}
                        >
                            <div className="d-flex align-items-start gap-2 mb-2">
                                <span style={{ fontSize: '1.4rem', lineHeight: 1 }}>🚀</span>
                                <div>
                                    <div className="fw-semibold" style={{ color: '#1a3a5c' }}>
                                        Try the live demo
                                    </div>
                                    <div className="text-muted" style={{ fontSize: '0.82rem' }}>
                                        No account needed. A private workspace is created for you instantly —
                                        watch the AI agent reorganise a messy vault in real time.
                                    </div>
                                </div>
                            </div>
                            <button
                                type="button"
                                className="btn w-100 py-2 fw-semibold"
                                style={{
                                    background: 'linear-gradient(135deg, #405d83 0%, #2c4a6e 100%)',
                                    color: '#fff',
                                    border: 'none',
                                }}
                                disabled={anyPending}
                                onClick={() => guestLogin()}
                            >
                                {isGuestPending
                                    ? <><span className="spinner-border spinner-border-sm me-2" />Setting up your demo…</>
                                    : '▶ Launch demo'}
                            </button>

                            {guestError && (
                                <div className="alert alert-danger mt-2 mb-0 py-2 small" role="alert">
                                    {guestError.response?.status === 429
                                        ? 'Too many attempts — please wait a few minutes and try again.'
                                        : 'Could not start the demo. Please try again.'}
                                </div>
                            )}
                        </div>
                    )}

                    {/* ── Login form ── */}
                    <form onSubmit={handleSubmit}>
                        {demoEnabled && (
                            <div className="text-center text-muted mb-3" style={{ fontSize: '0.82rem' }}>
                                — or sign in with your account —
                            </div>
                        )}

                        <div className="mb-3">
                            <label htmlFor="username" className="form-label">Username</label>
                            <input
                                id="username"
                                name="username"
                                type="text"
                                placeholder="e.g. admin"
                                required
                                className="form-control form-control-lg"
                                autoComplete="username"
                                disabled={anyPending}
                            />
                        </div>
                        <div className="mb-3">
                            <label htmlFor="password" className="form-label">Password</label>
                            <input
                                id="password"
                                name="password"
                                type="password"
                                placeholder="Enter password"
                                required
                                className="form-control form-control-lg"
                                autoComplete="current-password"
                                disabled={anyPending}
                            />
                        </div>

                        {error && (
                            <div className="alert alert-danger mt-3" role="alert">
                                {error.response?.status === 401
                                    ? 'Incorrect username or password.'
                                    : 'An unexpected error occurred.'}
                            </div>
                        )}

                        <button
                            type="submit"
                            className="btn btn-primary w-100 mt-2 py-2"
                            disabled={anyPending}
                        >
                            {isPending ? 'Signing in…' : 'Sign in'}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}