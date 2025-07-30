import React from 'react';
import { Form } from 'react-bootstrap';

/**
 * NodeEditor ist eine "dumme" UI-Komponente (V3-Version).
 * Ihre einzige Aufgabe ist es, eine Textarea anzuzeigen und Änderungen
 * des Inhalts an die Elternkomponente zurückzumelden.
 *
 * Die Logik für Speichern/Abbrechen liegt in der Elternkomponente.
 */
export default function NodeEditor({ content, onContentChange }) {
    return (
        // Wir können das `<div>` entfernen und direkt die Form.Control zurückgeben.
        <Form.Control
            as="textarea"
            value={content}
            onChange={(e) => onContentChange(e.target.value)}
            // Wir geben eine sinnvolle Höhe, die sich an den Inhalt anpasst
            style={{ minHeight: '60vh' }}
            className="mb-2"
            // Auto-Fokus, damit der User direkt lostippen kann
            autoFocus
        />
    );
}