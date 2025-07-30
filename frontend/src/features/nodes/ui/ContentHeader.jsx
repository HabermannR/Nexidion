import React from 'react';
import { Button } from 'react-bootstrap';
import './ContentHeader.css'; // Wir brauchen auch das zugehörige CSS

/**
 * Zeigt den Header des Inhaltsbereichs an (V3-Version).
 * Enthält den Titel des aktuellen Nodes und den "Bearbeiten"-Button.
 * Die Komponente ist "dumm" und erhält alle Daten und Handler als Props.
 */
export default function ContentHeader({ title, isEditing, onEditClick }) {
    return (
        <div className="content-header-container">
            {/* Der Titel wird einfach nur angezeigt */}
            <h1 className="content-title mb-0">{title}</h1>

            {/* Die Action-Buttons werden nur angezeigt, wenn wir NICHT im Edit-Modus sind. */}
            {!isEditing && (
                <div className="action-buttons">
                    {/*
            Der "Bearbeiten"-Button ist ein einfacher Button,
            da er nur einen lokalen State in der Elternkomponente (NodeContent) ändert.
            Er löst KEINE Server-Aktion aus.
          */}
                    <Button
                        variant="primary"
                        size="sm"
                        onClick={onEditClick}
                    >
                        Bearbeiten
                    </Button>
                </div>
            )}
        </div>
    );
}