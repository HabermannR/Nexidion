// src/components/nodes/VersionHistory.jsx (KORRIGIERTE VERSION)

import React from 'react';
import ListGroup from 'react-bootstrap/ListGroup';
import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import { BsArrowLeftRight } from 'react-icons/bs'; 

export default function VersionHistory({ 
  versions, 
  diffSelection, 
  onSelectVersion,   // NEU
  onCompareVersion,  // NEU
  onShowCurrent 
}) {

  if (!versions || versions.length === 0) {
    return (
      <div className="version-history-panel">
        <h5>Versionen</h5>
        <Alert variant="info" className="mt-2 small">
          Für diesen Node existieren keine früheren Versionen.
        </Alert>
      </div>
    );
  }
  
  const { base, compare } = diffSelection;

  return (
    <div className="version-history-panel">
      <h5>Versionen</h5>
      
      {base && (
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
        {versions.map(v => {
          const isBase = base?.timestamp === v.timestamp;
          const isCompare = compare?.timestamp === v.timestamp;
          
          // Das Diff-Symbol wird nur angezeigt, wenn eine Basis ausgewählt ist 
          // und das aktuelle Item nicht die Basis selbst ist.
          const showDiffButton = base && !isBase;

          return (
            <ListGroup.Item 
              key={v.timestamp}
              // Die 'active'-Prop von Bootstrap wird nur für die Basis-Auswahl genutzt (dunkelblau)
              active={isBase}
              // Unsere eigene Klasse für die hellblaue Vergleichs-Auswahl
              className={`d-flex justify-content-between align-items-center version-list-item ${isCompare ? 'diff-compare-active' : ''}`}
              // Klick auf den Hauptbereich wählt nur die Version zur Anzeige aus
              onClick={() => onSelectVersion(v)}
            >
              <div className="flex-grow-1">
                <span>Gespeichert am {new Date(v.timestamp).toLocaleString('de-DE')}</span>
                <br/>
                <small className="text-muted">v{v.version}</small>
              </div>
              
              {showDiffButton && (
                <Button 
                  variant={isCompare ? "primary" : "outline-info"}
                  size="sm"
                  className="ms-2"
                  onClick={(e) => {
                    e.stopPropagation(); // Verhindert, dass onSelectVersion auch ausgelöst wird
                    onCompareVersion(v); // Ruft den spezifischen Vergleichs-Handler auf
                  }}
                  title={`Vergleiche mit v${base.version}`}
                >
                  <BsArrowLeftRight />
                </Button>
              )}
            </ListGroup.Item>
          );
        })}
      </ListGroup>
    </div>
  );
}