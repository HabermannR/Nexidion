// src/components/AppLoading.jsx
import React from 'react';

// Dies könnte später ein schöner Spinner von Bootstrap sein.
export default function AppLoading() {
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            fontSize: '1.5rem',
            color: '#6c757d'
        }}>
            Anwendung wird geladen...
        </div>
    );
}