// src/components/DiffViewer.jsx (NEUE DATEI)

import React, { useEffect, useRef } from 'react';
import { createPatch } from 'diff';
import { Diff2HtmlUI } from 'diff2html/lib/ui/js/diff2html-ui';

// Wichtig: Die CSS-Imports müssen hier sein!
import 'highlight.js/styles/github.css';
import 'diff2html/bundles/css/diff2html.min.css';

const DiffViewer = ({ oldContent, newContent, oldTitle = 'Original', newTitle = 'Vergleich' }) => {
    const diffContainerRef = useRef(null);

    useEffect(() => {
        if (diffContainerRef.current) {
            // Container leeren, bevor neu gezeichnet wird
            diffContainerRef.current.innerHTML = '';

            // Sicherstellen, dass wir keine null/undefined Werte haben
            const safeOldContent = oldContent || '';
            const safeNewContent = newContent || '';

            // Nichts tun, wenn beide leer sind
            if (safeOldContent === '' && safeNewContent === '') {
                return;
            }

            // NEUE PRÜFUNG: Wenn Inhalte identisch sind, zeige eine Meldung an.
            if (safeOldContent === safeNewContent) {
                diffContainerRef.current.innerHTML = `
                    <div class="alert alert-success m-3">
                        Keine Unterschiede zwischen den ausgewählten Versionen gefunden.
                    </div>
                `;
                return; // Beende die Funktion hier
            }

            // Den Patch-String erstellen
            const diffString = createPatch(
                'node-content.md', // Dateiname ist nur für die Anzeige
                safeOldContent,
                safeNewContent,
                oldTitle,
                newTitle,
                { context: 9999 } // Zeigt den gesamten Kontext
            );

            // Konfiguration für die Anzeige
            const configuration = {
                drawFileList: false,
                matching: 'lines',
                outputFormat: 'side-by-side', // oder 'line-by-line'
                highlight: true,
                renderNothingWhenEmpty: true // Wichtig
            };

            // UI-Instanz erstellen und zeichnen
            const diff2htmlUi = new Diff2HtmlUI(diffContainerRef.current, diffString, configuration);
            diff2htmlUi.draw();
            diff2htmlUi.highlightCode();
        }
    }, [oldContent, newContent, oldTitle, newTitle]);

    // Ein einfacher div, der als Mount-Point für diff2html dient
    return (
        <div ref={diffContainerRef}></div>
    );
};

export default DiffViewer;