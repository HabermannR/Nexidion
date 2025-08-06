// IN: src/features/workspace/center-panel/MarkdownRenderer.jsx

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// NEU: Wir importieren die ResizableImage-Komponente anstelle von SecureImage.
// Sie enthält bereits die SecureImage-Logik.
import ResizableImage from '../../../components/ResizableImage'; // Passe den Pfad ggf. an

import './MarkdownRenderer.css';

/**
 * Eine Wrapper-Komponente, die einen Markdown-String entgegennimmt
 * und ihn als formatiertes HTML rendert.
 *
 * NEU: Sie fängt alle `<img>`-Tags ab und rendert sie über die
 * `ResizableImage`-Komponente, die sowohl sicheres Laden als auch
 * interaktive Größenanpassung ermöglicht.
 */
export default function MarkdownRenderer({ content }) {
    if (!content) {
        return (
            <div className="p-4 bg-light rounded text-muted">
                Dieses Dokument hat keinen Inhalt.
            </div>
        );
    }

    const markdownComponents = {
        // Jedes Mal, wenn ReactMarkdown auf ein Bild stößt, wird diese Funktion aufgerufen.
        img: ({ node, ...props }) => {
            // ==========================================================
            // DIE EINZIGE ÄNDERUNG: Wir verwenden jetzt den Wrapper.
            // ==========================================================
            // Wir geben die Props einfach an unsere neue ResizableImage-Komponente weiter.
            return <ResizableImage {...props} />;
        }
    };

    return (
        <div className="markdown-body">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}