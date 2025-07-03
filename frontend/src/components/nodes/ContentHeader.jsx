// src/components/nodes/ContentHeader.jsx (FINALE VERSION)

import React from 'react';
import Button from 'react-bootstrap/Button';
import './ContentHeader.css'; // Wir fügen eine dedizierte CSS-Datei hinzu

/**
 * Zeigt den Header des Inhaltsbereichs an.
 * Enthält den Titel des aktuellen Nodes und die primären Aktionen.
 */
export default function ContentHeader({ title, isEditing, onEditClick, onRenameClick }) {
  return (
    <div className="content-header-container">
      <h2 className="content-title mb-0">{title}</h2>
      
      {/* Die Action-Buttons werden nur angezeigt, wenn wir nicht im Edit-Modus sind. */}
      {!isEditing && (
        <div className="action-buttons">
          <Button variant="secondary" size="sm" onClick={onRenameClick}>Umbenennen</Button>
          <Button variant="primary" size="sm" onClick={onEditClick}>Bearbeiten</Button>
        </div>
      )}
    </div>
  );
}