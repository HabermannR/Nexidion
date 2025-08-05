// src/components/DiffViewer.jsx

import React, { useMemo } from 'react';
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued-react19';

// Die CSS-Imports der alten Komponente sind nicht mehr nötig!
// react-diff-viewer kümmert sich intern um das Styling.

const DiffViewer = ({
                                oldContent,
                                newContent,
                                oldTitle = 'Original',
                                newTitle = 'Vergleich',
                                splitView = true, // Neue Prop: Standardmäßig Split-View
                                useDarkTheme = false, // Neue Prop: Dark Mode
                            }) => {
    // Sicherstellen, dass wir keine null/undefined Werte haben
    const safeOldContent = oldContent || '';
    const safeNewContent = newContent || '';

    // Nichts tun, wenn beide leer sind
    if (safeOldContent === '' && safeNewContent === '') {
        return (
            <div className="alert alert-info m-3">
                Keine Inhalte zum Vergleichen vorhanden.
            </div>
        );
    }

    // Wenn Inhalte identisch sind, zeige eine Meldung an.
    // react-diff-viewer würde dies auch tun, aber eine explizite Meldung ist oft benutzerfreundlicher.
    if (safeOldContent === safeNewContent) {
        return (
            <div className="alert alert-success m-3">
                Keine Unterschiede zwischen den ausgewählten Versionen gefunden.
            </div>
        );
    }

    // Optional: Definiere benutzerdefinierte Styles, um das Aussehen anzupassen.
    // Dies ist ein riesiger Vorteil gegenüber der alten Methode!
    // Wir verwenden useMemo, um zu verhindern, dass das Objekt bei jedem Render neu erstellt wird.
    const customStyles = useMemo(() => ({
        variables: {
            dark: {
                diffViewerBackground: '#1e1e1e',
                addedBackground: '#0a3d13',
                removedBackground: '#5c1212',
            },
        },
        line: {
            padding: '10px 2px',
            '&:hover': {
                background: useDarkTheme ? '#2a2a2a' : '#f0f0f0',
            },
        },
        gutter: {
            minWidth: '40px',
        },
        marker: {
            width: '20px',
        }
    }), [useDarkTheme]);

    return (
        <ReactDiffViewer
            oldValue={safeOldContent}
            newValue={safeNewContent}
            leftTitle={oldTitle}
            rightTitle={newTitle}
            splitView={splitView}
            useDarkTheme={useDarkTheme}
            compareMethod={DiffMethod.WORDS} // Bessere Vergleichsmethode für Text

            // === Weitere nützliche "aufgebohrte" Features ===

            // Blendet lange, unveränderte Abschnitte aus und zeigt einen "Expand"-Button.
            showDiffOnly={true}
            extraLinesSurroundingDiff={3} // Zeigt 3 Zeilen Kontext um eine Änderung herum

            // Schaltet die Hervorhebung einzelner Wörter an/aus
            disableWordDiff={false}

            // Wende unsere optionalen Custom-Styles an
            styles={customStyles}
        />
    );
};

export default DiffViewer;