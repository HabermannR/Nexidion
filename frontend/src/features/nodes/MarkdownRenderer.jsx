import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw'; // WICHTIG: Neues Plugin importieren

import wikiLinkPlugin from '@nexidion/remark-internal-links';
import InternalLink from './InternalLink';
import ResizableImage from '../../components/ResizableImage.jsx';
import './MarkdownRenderer.css';

export default function MarkdownRenderer({ content }) {
    const markdownComponents = {
        // Wir fangen alle <span>-Tags ab.
        span: ({ node, children, ...props }) => {
            // Wir prüfen, ob es einer unserer speziellen Links ist.
            if (props['data-target']) {
                const target = decodeURIComponent(props['data-target']);
                const displayText = decodeURIComponent(props['data-display-text']);

                // Wir rendern unsere intelligente React-Komponente.
                return <InternalLink target={target} displayText={displayText} />;
            }

            // Ansonsten ist es ein normaler Span, den wir einfach durchreichen.
            return <span {...props}>{children}</span>;
        },

        // Die anderen Renderer bleiben wie gewohnt.
        img: ({ node, ...props }) => <ResizableImage {...props} />,
        a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    };

    return (
        <div className="markdown-body">
            <ReactMarkdown
                remarkPlugins={[remarkGfm, wikiLinkPlugin]}
                // WICHTIG: Erlaube das Rendern von rohem HTML, das unser Plugin erzeugt.
                rehypePlugins={[rehypeRaw]}
                components={markdownComponents}
            >
                {content || ''}
            </ReactMarkdown>
        </div>
    );
}