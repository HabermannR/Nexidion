import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';

// Import der Unterkomponenten
import DiffViewer from '../common/DiffViewer';
import ContentHeader from '../../../features/workspace/center-panel/ContentHeader.jsx';
import NodeEditor from '../../../features/workspace/center-panel/NodeEditor.jsx';
import ResizableImage from '../common/ResizableImage.jsx'; 

// Import der CSS-Datei
import './ContentArea.css';

export default function ContentArea({
    node,
    onSave,
    onRename,
    onLinkClick, // Handler für [[Links]]
    successMessage,
    isEditing,
    onSetIsEditing,
    editableContent,
    onContentChange,
    onCancelEdit,
    contentToDisplay, // Inhalt für die Einzelansicht (aktuell oder alt)
    versionForDiffBase,
    versionForDiffCompare,
    onShowCurrent
}) {

	// Diese Hilfsfunktion scannt Text und wandelt [[Links]] in klickbare Elemente um.
	const renderTextWithInternalLinks = (children) => {
		return React.Children.map(children, child => {
			// Wir verarbeiten nur reine Text-Knoten für unsere Link-Syntax.
			if (typeof child === 'string') {
				const linkRegex = /\[\[\s*([^|\]\s][^|\]]*?)\s*(?:\|\s*(.+?)\s*)?\]\](\w*)?/g;
				const parts = [];
				let lastIndex = 0;
				const matches = [...child.matchAll(linkRegex)];

				if (matches.length === 0) {
					return child; // Kein Link gefunden, den Originaltext zurückgeben.
				}

				matches.forEach((match, index) => {
					const [fullMatch, target, displayText, suffix] = match;
					const matchIndex = match.index;

					// Text vor dem Link hinzufügen
					if (matchIndex > lastIndex) {
						parts.push(child.substring(lastIndex, matchIndex));
					}

					// Der finale Text, der im Link angezeigt werden soll.
					// Wir kombinieren den Alias (displayText) oder das Ziel (target) mit dem Suffix.
					const finalDisplayText = (displayText || target) + (suffix || '');

					// STABILE LÖSUNG:
					// Wir erstellen ein einfaches <span> mit dem Text.
					// Wir verzichten auf eine weitere Runde Markdown-Verarbeitung hier drin.
					parts.push(
						<span key={`${target}-${index}`} onClick={() => onLinkClick(target)} className="internal-link">
							{finalDisplayText}
						</span>
					);

					lastIndex = matchIndex + fullMatch.length;
				});

				// Restlichen Text nach dem letzten Link hinzufügen
				if (lastIndex < child.length) {
					parts.push(child.substring(lastIndex));
				}

				return parts;
			}

			// Für bereits existierende React-Elemente (z.B. ein <strong>-Tag vom Parser),
			// rufen wir die Funktion rekursiv für deren Kinder auf.
			if (React.isValidElement(child) && child.props.children) {
				return React.cloneElement(child, { children: renderTextWithInternalLinks(child.props.children) });
			}

			// Alle anderen Kinder (z.B. null) unverändert zurückgeben.
			return child;
		});
	};    // Konfiguration für ReactMarkdown, um unsere Link-Logik und resizable Bilder zu nutzen.
    const componentRenderers = {
        p: ({ node, ...props }) => <p {...props}>{renderTextWithInternalLinks(props.children)}</p>,
        li: ({ node, ...props }) => <li {...props}>{renderTextWithInternalLinks(props.children)}</li>,
        h1: ({ node, ...props }) => <h1 {...props}>{renderTextWithInternalLinks(props.children)}</h1>,
        h2: ({ node, ...props }) => <h2 {...props}>{renderTextWithInternalLinks(props.children)}</h2>,
        h3: ({ node, ...props }) => <h3 {...props}>{renderTextWithInternalLinks(props.children)}</h3>,
		h4: ({ node, ...props }) => <h4 {...props}>{renderTextWithInternalLinks(props.children)}</h4>,
		h5: ({ node, ...props }) => <h5 {...props}>{renderTextWithInternalLinks(props.children)}</h5>,
		h6: ({ node, ...props }) => <h6 {...props}>{renderTextWithInternalLinks(props.children)}</h6>,
        td: ({ node, ...props }) => <td {...props}>{renderTextWithInternalLinks(props.children)}</td>,
		th: ({ node, ...props }) => <th {...props}>{renderTextWithInternalLinks(props.children)}</th>,

		img: ResizableImage,  
    };

    // Fallback, wenn kein Node ausgewählt ist.
    if (!node) {
        return (
            <div className="p-5 text-center text-muted">
                <h1>Willkommen</h1>
                <p>Wähle einen Node aus dem Baum aus, um den Inhalt anzuzeigen.</p>
            </div>
        );
    }

    const isDiffMode = !!(versionForDiffBase && versionForDiffCompare);

    let olderVersion = null;
    let newerVersion = null;

    if (isDiffMode) {
        olderVersion = versionForDiffBase.version < versionForDiffCompare.version
            ? versionForDiffBase
            : versionForDiffCompare;

        newerVersion = versionForDiffBase.version > versionForDiffCompare.version
            ? versionForDiffBase
            : versionForDiffCompare;
    }

    return (
        <div className="content-area-wrapper p-3">
            <ContentHeader
                title={node.title}
                isEditing={isEditing}
                onEditClick={() => {
                    onContentChange(contentToDisplay);
                    onSetIsEditing(true);
                }}
                onRenameClick={() => {
                    const newTitle = prompt("Neuen Titel eingeben für:", node.title);
                    if (newTitle && newTitle.trim() && newTitle.trim() !== node.title) {
                        onRename(node.id, newTitle.trim());
                    }
                }}
                disableActions={isDiffMode || !!versionForDiffBase} // Aktionen auch bei Einzel-Version-Ansicht sperren
            />

            {successMessage && <Alert variant="success" className="mt-3">{successMessage}</Alert>}

            {/* ZUSTAND 1: DIFF-ANSICHT */}
            {isDiffMode ? (
                <div className="mt-3">
                    {/* =================================================================== */}
                    {/* NEU: Hinzufügen einer Alert-Box mit "Zurück"-Button für den Diff-Modus */}
                    {/* =================================================================== */}
                    <Alert variant="secondary" className="mb-3 small">
                        <div className="d-flex justify-content-between align-items-center">
                            <span>
                                Du vergleichst Version <strong>{olderVersion.version}</strong> mit Version <strong>{newerVersion.version}</strong>.
                            </span>
                            <Button
                                variant="outline-dark"
                                size="sm"
                                onClick={onShowCurrent} // Derselbe Handler wird hier wiederverwendet
                            >
                                Vergleich beenden
                            </Button>
                        </div>
                    </Alert>

                    <DiffViewer
                        oldContent={olderVersion.content}
                        newContent={newerVersion.content}
                        oldTitle={`v${olderVersion.version} (älter) - ${new Date(olderVersion.timestamp).toLocaleString('de-DE')}`}
                        newTitle={`v${newerVersion.version} (neuer) - ${new Date(newerVersion.timestamp).toLocaleString('de-DE')}`}
                    />
                </div>

            /* ZUSTAND 2 & 3: NORMALE ANSICHT (alt oder aktuell) / EDITOR */
            ) : (
                <>
                    {/* Dieser Teil ist bereits korrekt */}
                    {versionForDiffBase && !isDiffMode && (
                        <Alert variant="info" className="mt-3 small">
                            <div className="d-flex justify-content-between align-items-center">
                                <span>
                                    Du betrachtest Version <strong>{versionForDiffBase.version}</strong> vom {new Date(versionForDiffBase.timestamp).toLocaleString('de-DE')}.
                                </span>
                                <Button
                                    variant="outline-primary"
                                    size="sm"
                                    onClick={onShowCurrent}
                                >
                                    Zurück zur aktuellen Version
                                </Button>
                            </div>
                        </Alert>
                    )}

                    <NodeEditor
                        isEditing={isEditing}
                        content={isEditing ? editableContent : contentToDisplay}
                        onContentChange={onContentChange}
                        onSave={onSave}
                        onCancel={onCancelEdit}
                        renderViewMode={() => (
                            <div className="view-content mt-3 markdown-content">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={componentRenderers}
                                >
                                    {contentToDisplay || ''}
                                </ReactMarkdown>
                            </div>
                        )}
                    />
                </>
            )}
        </div>
    );
}