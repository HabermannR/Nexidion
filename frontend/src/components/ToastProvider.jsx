// src/components/ToastProvider.jsx
//
// A single, app-wide toast system.
//
// Usage anywhere in the tree:
//   import { useToast } from './ToastProvider';
//   const toast = useToast();
//   toast.error('Something went wrong');
//   toast.success('Saved!');
//   toast.info('FYI...');
//   toast.warn('Watch out');

import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { Toast, ToastContainer } from 'react-bootstrap';

const ToastContext = createContext(null);

let _externalPush = null;

/**
 * Call this from outside React (e.g. in apiClient.js interceptors).
 * Works after ToastProvider has mounted at least once.
 */
export function pushToast(variant, message) {
    if (_externalPush) _externalPush(variant, message);
    else console.warn('[Toast] Provider not mounted yet:', message);
}

export function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);
    const idRef = useRef(0);

    const push = useCallback((variant, message) => {
        const id = ++idRef.current;
        setToasts(prev => [...prev, { id, variant, message }]);
        setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id));
        }, 5000);
    }, []);

    // Expose to module-level helper
    _externalPush = push;

    const ctx = {
        success: (msg) => push('success', msg),
        error:   (msg) => push('danger',  msg),
        warn:    (msg) => push('warning', msg),
        info:    (msg) => push('info',    msg),
    };

    return (
        <ToastContext.Provider value={ctx}>
            {children}

            {/* Fixed bottom-right stack */}
            <ToastContainer
                position="bottom-end"
                className="p-3"
                style={{ zIndex: 9999 }}
            >
                {toasts.map(t => (
                    <Toast
                        key={t.id}
                        bg={t.variant}
                        onClose={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
                        show
                        delay={5000}
                        autohide
                    >
                        <Toast.Header>
                            <strong className="me-auto">
                                {t.variant === 'danger'  && '⚠ Error'}
                                {t.variant === 'success' && '✓ Success'}
                                {t.variant === 'warning' && '⚠ Warning'}
                                {t.variant === 'info'    && 'ℹ Info'}
                            </strong>
                        </Toast.Header>
                        <Toast.Body className={t.variant === 'danger' || t.variant === 'success' ? 'text-white' : ''}>
                            {t.message}
                        </Toast.Body>
                    </Toast>
                ))}
            </ToastContainer>
        </ToastContext.Provider>
    );
}

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
    return ctx;
}
