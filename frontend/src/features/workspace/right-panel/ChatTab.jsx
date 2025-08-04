// src/features/workspace/right-panel/ChatTab.jsx
import React from 'react';
import { Form } from 'react-bootstrap';

export default function ChatTab({ nodeId }) {
    return (
        <div className="p-3">
            <h6 className="text-muted">Chat</h6>
            <p className="small">Chat-Funktionalität für Node <strong>{nodeId || 'N/A'}</strong>.</p>
            <Form.Control as="textarea" rows={3} placeholder="Stelle eine Frage..." />
        </div>
    );
}