// src/components/modals/UpdatePreviewModal.jsx (FINALE, KORREKTE VERSION)

import React, { useEffect, useRef } from 'react';
import Modal from 'react-bootstrap/Modal';
import Button from 'react-bootstrap/Button';
import { createPatch } from 'diff';

// Korrekter Import für die UI-Klasse
import { Diff2HtmlUI } from 'diff2html/lib/ui/js/diff2html-ui-slim.js';

// Wichtig: Die CSS-Dateien importieren
import 'highlight.js/styles/github.css'; // oder ein anderes Theme Ihrer Wahl
import 'diff2html/bundles/css/diff2html.min.css';

const UpdatePreviewModal = ({ show, onHide, onAccept, oldContent, newContent, isUpdating }) => {
  // Wir brauchen eine Referenz auf das DOM-Element, in das das Diff gerendert wird
  const diffContainerRef = useRef(null);

  // useEffect wird immer dann ausgeführt, wenn sich die Inhalte ändern
  useEffect(() => {
    // Nur ausführen, wenn das Modal sichtbar ist und das Container-Element existiert
    if (show && diffContainerRef.current) {
      const safeOldContent = oldContent || '';
      const safeNewContent = newContent || '';

      // 1. Erstelle den Patch-String (das "unified diff" Format)
      const diffString = createPatch(
        'node-content.md', // Dateiname ist für die Darstellung hilfreich
        safeOldContent,
        safeNewContent,
        'Original', // Header für alte Version
        'Vorschlag', // Header für neue Version
        { context: 9999 } // Zeigt den gesamten Kontext, nicht nur geänderte Zeilen
      );
      
      // 2. Konfiguration für Diff2HtmlUI
      const configuration = {
        drawFileList: false, // Wir haben nur eine "Datei", also brauchen wir keine Liste
        matching: 'lines',
        outputFormat: 'side-by-side', // Nebeneinander-Ansicht
        highlight: true, // Syntax-Highlighting aktivieren
        renderNothingWhenEmpty: true, // Nichts anzeigen, wenn es keine Änderungen gibt
      };

      // 3. Erstelle eine Instanz der UI-Klasse
      const diff2htmlUi = new Diff2HtmlUI(diffContainerRef.current, diffString, configuration);
      
      // 4. Zeichne das Diff und führe das Highlighting aus
      diff2htmlUi.draw();
      diff2htmlUi.highlightCode();
    }
  }, [show, oldContent, newContent]); // Abhängigkeiten des Effekts

  return (
    <Modal show={show} onHide={onHide} size="xl" centered>
      <Modal.Header closeButton>
        <Modal.Title>AI Update Proposal</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {/*
          Wir übergeben das leere `div` mit der Referenz.
          Der `useEffect`-Hook wird dieses Div mit dem Diff-Inhalt füllen.
        */}
        <div ref={diffContainerRef}></div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>
          Cancel
        </Button>
        <Button variant="primary" onClick={onAccept} disabled={isUpdating}>
          {isUpdating ? 'Saving...' : 'Accept & Save Changes'}
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default UpdatePreviewModal;