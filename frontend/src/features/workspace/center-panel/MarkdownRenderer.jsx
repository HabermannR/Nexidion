// src/features/workspace/center-panel/MarkdownRenderer.jsx

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Optional: Füge hier etwas Basis-Styling für gerendertes Markdown hinzu.
// Du kannst diese CSS-Datei erstellen oder die Stile in eine globale CSS-Datei packen.
import './MarkdownRenderer.css';

/**
 * Eine Wrapper-Komponente, die einen Markdown-String entgegennimmt
 * und ihn als formatiertes HTML rendert.
 */
export default function MarkdownRenderer({ content }) {
    if (!content) {
        return (
            <div className="p-4 bg-light rounded text-muted">
                Dieses Dokument hat keinen Inhalt.
            </div>
        );
    }

    return (
        <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
            </ReactMarkdown>
        </div>
    );
}