// src/components/nodes/ContentArea.jsx

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Alert from 'react-bootstrap/Alert';

// Import der Unterkomponenten
import ContentHeader from './ContentHeader.jsx';
import NodeEditor from './NodeEditor.jsx';
import IFSLandkarte from '../special_nodes/IFSLandkarte.jsx';
import ResizableImage from '../common/ResizableImage.jsx'; 

// Import der CSS-Datei
import './ContentArea.css';

export default function ContentArea({
    node,
    onSave,
    onRename,
    onLinkClick, // Dieser Prop ist der entscheidende Klick-Handler
    successMessage,
    isEditing,
    editableContent,
    onSetIsEditing,
    onContentChange,
    onCancelEdit,
    contentToDisplay
}) {

    // Diese Hilfsfunktion scannt Text-Kinder und ersetzt [[Link]]-Syntax.
    const renderTextWithInternalLinks = (children) => {
        return React.Children.map(children, child => {
            if (typeof child === 'string') {
                const linkRegex = /\[\[\s*([^|\]\s][^|\]]*?)\s*(?:\|\s*(.+?)\s*)?\]\]/g;
                const parts = [];
                let lastIndex = 0;
                const matches = [...child.matchAll(linkRegex)];

                if (matches.length === 0) { return child; }

                matches.forEach((match, index) => {
                    const [fullMatch, target, displayText] = match;
                    const matchIndex = match.index;

                    if (matchIndex > lastIndex) {
                        parts.push(child.substring(lastIndex, matchIndex));
                    }
                    // WICHTIG: Der onClick hier ruft jetzt den übergebenen Handler auf!
                    parts.push(
                        <span key={`${target}-${index}`} onClick={() => onLinkClick(target)} className="internal-link">
                            {displayText || target}
                        </span>
                    );
                    lastIndex = matchIndex + fullMatch.length;
                });

                if (lastIndex < child.length) {
                    parts.push(child.substring(lastIndex));
                }
                return parts;
            }
            if (React.isValidElement(child) && child.props.children) {
                return React.cloneElement(child, { children: renderTextWithInternalLinks(child.props.children) });
            }
            return child;
        });
    };

    // Dieses Objekt wird an ReactMarkdown übergeben, um das Standard-Rendering zu überschreiben.
    const componentRenderers = {
        // Wir wenden unsere Link-Logik auf alle diese Elemente an.
        p: ({ node, ...props }) => <p {...props}>{renderTextWithInternalLinks(props.children)}</p>,
        li: ({ node, ...props }) => <li {...props}>{renderTextWithInternalLinks(props.children)}</li>,
        h1: ({ node, ...props }) => <h1 {...props}>{renderTextWithInternalLinks(props.children)}</h1>,
        h2: ({ node, ...props }) => <h2 {...props}>{renderTextWithInternalLinks(props.children)}</h2>,
        h3: ({ node, ...props }) => <h3 {...props}>{renderTextWithInternalLinks(props.children)}</h3>,
        // Du kannst das für weitere Elemente wie h4, blockquote etc. erweitern.
        img: ResizableImage, 
    };
    // =========================================================================
    // == ENDE DER KORREKTUR ==
    // =========================================================================

    if (!node) {
        return (
            <div className="p-5 text-center text-muted">
                <h1>Willkommen</h1>
                <p>Wähle einen Node aus dem Baum aus, um den Inhalt anzuzeigen.</p>
            </div>
        );
    }

    return (
        // Dieser Wrapper ist nützlich für das Padding und Styling der gesamten Spalte
        <div className="content-area-wrapper p-3">
            <ContentHeader
                title={node.title}
                isEditing={isEditing}
                onEditClick={() => onSetIsEditing(true)}
                onRenameClick={() => {
                    const newTitle = prompt("Neuen Titel eingeben für:", node.title);
                    if (newTitle && newTitle.trim() && newTitle.trim() !== node.title) {
                        onRename(node.id, newTitle.trim());
                    }
                }}
            />

            {successMessage && <Alert variant="success" className="mt-3">{successMessage}</Alert>}

            {node.title === 'IFS Landkarte' ? (
                <IFSLandkarte onLinkClick={onLinkClick} />
            ) : (
                <NodeEditor
                    isEditing={isEditing}
                    content={editableContent}
                    onContentChange={onContentChange}
                    onSave={onSave}
                    onCancel={onCancelEdit}
                    renderViewMode={() => (
                        // Dieser Wrapper ist wichtig für spezifische CSS-Regeln für den View-Modus
                        <div className="view-content mt-3">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                // HIER wird die korrigierte Rendering-Logik jetzt verwendet
                                components={componentRenderers} 
                            >
                                {contentToDisplay || ''}
                            </ReactMarkdown>
                        </div>
                    )}
                />
            )}
        </div>
    );
}