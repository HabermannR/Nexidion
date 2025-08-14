// src/components/AppLoading.jsx
import React from 'react';
import Spinner from 'react-bootstrap/Spinner';

/**
 * A full-screen loading indicator component that displays a centered Bootstrap spinner
 * and a "loading" message.
 */
export default function AppLoading() {
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            fontSize: '1.5rem',
            color: '#6c757d',
            gap: '1rem' // Adds space between the spinner and the text
        }}>
            <Spinner animation="border" role="status">
                <span className="visually-hidden">Wird geladen...</span>
            </Spinner>
            <span>Anwendung wird geladen...</span>
        </div>
    );
}