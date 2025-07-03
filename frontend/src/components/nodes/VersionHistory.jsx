// src/components/nodes/VersionHistory.jsx (KORRIGIERTE VERSION)

import React from 'react';
import ListGroup from 'react-bootstrap/ListGroup';
import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';

export default function VersionHistory({ 
  versions, 
  selectedVersion, 
  onVersionClick, 
  onShowCurrent 
}) {

  if (!versions || versions.length === 0) {
    // ... (dieser Teil bleibt unverändert)
    return (
      <div className="version-history-panel">
        <h5>Versionen</h5>
        <Alert variant="info" className="mt-2 small">
          Für diesen Node existieren keine früheren Versionen.
        </Alert>
      </div>
    );
  }

  // ===================================================================
  // KORREKTUR: ENTFERNEN SIE DIESE ZEILE.
  // Das Backend liefert die Liste bereits korrekt sortiert (neueste oben).
  // const reversedVersions = versions.slice().reverse();
  // Wir verwenden jetzt direkt die `versions`-Prop.
  // ===================================================================

  return (
    <div className="version-history-panel">
      <h5>Versionen</h5>
      
      {selectedVersion && (
        <Button 
          variant="outline-secondary" 
          size="sm" 
          className="mb-2 w-100" 
          onClick={onShowCurrent}
        >
          Zurück zur aktuellen Version
        </Button>
      )}

      <ListGroup variant="flush" className="mt-2">
        {/* Wir iterieren jetzt direkt über die `versions`-Liste */}
        {versions.map(v => {
          const isSelected = selectedVersion && (selectedVersion.timestamp === v.timestamp);
          
          return (
            <ListGroup.Item 
              key={v.timestamp} 
              action 
              active={isSelected}
              onClick={() => onVersionClick(v)}
              className="d-flex justify-content-between align-items-center" // Für schöneres Layout
            >
              <span>Gespeichert am {new Date(v.timestamp).toLocaleString('de-DE')}</span>
              <small className="text-muted">v{v.version}</small> {/* Optional: Versionsnummer anzeigen */}
            </ListGroup.Item>
          );
        })}
      </ListGroup>
    </div>
  );
}