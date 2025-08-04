// src/features/workspace/right-panel/WorkflowTab.jsx
import React from 'react';
import { Button, Form } from 'react-bootstrap';
// Annahme: selectedNodeIds kommt aus einem globalen Context (z.B. Zustand oder React Context)
// Fürs Erste simulieren wir es.
const selectedNodeIds = { size: 3 };

export default function WorkflowTab() {
    return (
        <div className="p-3">
            <h6 className="text-muted">Workflows</h6>
            <p className="small">Workflows auf <strong>{selectedNodeIds.size}</strong> ausgewählte(n) Nodes anwenden.</p>
            <Form.Group className="mb-3">
                <Form.Label className="small">Vorlage</Form.Label>
                <Form.Select size="sm">
                    <option>Bubble Up Update</option>
                    <option>Export als EPUB</option>
                </Form.Select>
            </Form.Group>
            <div className="d-grid">
                <Button>Workflow starten</Button>
            </div>
        </div>
    );
}