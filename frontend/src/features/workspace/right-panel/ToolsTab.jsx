// src/features/workspace/right-panel/ToolsTab.jsx
import React from 'react';
import { Button } from 'react-bootstrap';

export default function ToolsTab({ nodeId }) {
    return (
        <div className="p-3">
            <h6 className="text-muted">Tools</h6>
            <p className="small">Spezifische Werkzeuge für Node <strong>{nodeId || 'N/A'}</strong>.</p>
            <div className="d-grid gap-2">
                <Button variant="outline-secondary" size="sm">Analyse starten</Button>
                <Button variant="outline-secondary" size="sm">Metadaten extrahieren</Button>
            </div>
        </div>
    );
}