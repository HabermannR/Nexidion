import React from 'react';
import { Container } from 'react-bootstrap';

export default function AdminDashboard() {
    return (
        <Container className="p-4">
            <h1>Admin Dashboard</h1>
            <p>Dieser Bereich ist nur für Administratoren sichtbar.</p>
            {/* Hier kämen Tabellen, Graphen etc. hin */}
        </Container>
    );
}