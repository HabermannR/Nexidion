// src/components/nodes/ContentHeader.jsx (FINALE VERSION mit Diff-Modus-Unterstützung)

import React from 'react';
import Button from 'react-bootstrap/Button';
import './ContentHeader.css';

/**
 * Zeigt den Header des Inhaltsbereichs an.
 * Enthält den Titel des aktuellen Nodes und die primären Aktionen.
 *
 * NEU: `disableActions` Prop, um die Buttons im Diff-Vergleichsmodus zu deaktivieren.
 */
export default function ContentHeader({ title, isEditing, onEditClick, onRenameClick, disableActions = false }) {
  return (
    <div className="content-header-container">
      <h2 className="content-title mb-0">{title}</h2>
      
      {/* Die Action-Buttons werden nur angezeigt, wenn wir nicht im Edit-Modus sind. */}
      {!isEditing && (
        <div className="action-buttons">
          <Button 
            variant="secondary" 
            size="sm" 
            onClick={onRenameClick}
            disabled={disableActions} // Hier wird die neue Prop verwendet
          >
            Umbenennen
          </Button>
          <Button 
            variant="primary" 
            size="sm" 
            onClick={onEditClick}
            disabled={disableActions} // Und hier auch
          >
            Bearbeiten
          </Button>
        </div>
      )}
    </div>
  );
}