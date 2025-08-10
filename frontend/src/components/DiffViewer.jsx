import React, { useMemo } from 'react';
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued-react19';
import { useIsMobile } from '../hooks/useIsMobile';

/**
 * Eine Wrapper-Komponente für `react-diff-viewer-continued-react19`, die mehrere
 * Probleme der Bibliothek behebt und eine responsive Darstellung ermöglicht.
 * (Dokumentation bleibt gleich)
 */
const DiffViewer = ({
                        oldContent,
                        newContent,
                        oldTitle = 'Original',
                        newTitle = 'Vergleich',
                        splitView = true,
                        useDarkTheme = false,
                    }) => {
    // ====================================================================
    // KORREKTUR: Alle Hooks an den Anfang der Komponente verschieben,
    // BEVOR irgendwelche Bedingungen oder 'return'-Anweisungen kommen.
    // ====================================================================
    const isMobile = useIsMobile();

    // Wir verwenden `useMemo`, um zu verhindern, dass das große Style-Objekt
    // bei jedem Render neu erstellt wird.
    const customStyles = useMemo(() => ({
        diffContainer: {
            minWidth: '0',
        },
        contentText: {
            fontSize: '0.75rem',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
        },
        variables: {
            dark: {
                diffViewerBackground: '#1e1e1e',
                addedBackground: '#0a3d13',
                removedBackground: '#5c1212',
            },
        },
    }), []); // Leeres Array, da die Styles nicht von Props abhängen.


    // Sicherstellen, dass wir keine null/undefined Werte an die Bibliothek übergeben.
    const safeOldContent = oldContent || '';
    const safeNewContent = newContent || '';

    // Guard Clauses können jetzt sicher hier stehen, da alle Hooks bereits aufgerufen wurden.
    if (safeOldContent === '' && safeNewContent === '') {
        return <div className="alert alert-info m-3">Keine Inhalte zum Vergleichen vorhanden.</div>;
    }

    if (safeOldContent === safeNewContent) {
        return <div className="alert alert-success m-3">Keine Unterschiede zwischen den ausgewählten Versionen gefunden.</div>;
    }

    return (
        <ReactDiffViewer
            oldValue={safeOldContent}
            newValue={safeNewContent}
            leftTitle={oldTitle}
            rightTitle={newTitle}
            useDarkTheme={useDarkTheme}
            splitView={!isMobile && splitView}
            hideLineNumbers={isMobile}
            compareMethod={DiffMethod.WORDS}
            showDiffOnly={true}
            extraLinesSurroundingDiff={3}
            disableWordDiff={false}
            styles={customStyles}
        />
    );
};

export default DiffViewer;