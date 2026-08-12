import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';

import wikiLinkPlugin from '@nexidion/remark-internal-links';
import InternalLink from './InternalLink';
import ResizableImage from '../../components/ResizableImage.jsx';
import './MarkdownRenderer.css';

export default function MarkdownRenderer({ content }) {
    const sanitizeSchema = {
        ...defaultSchema,
        attributes: {
            ...defaultSchema.attributes,
            span: [...(defaultSchema.attributes?.span || []), 'className', 'data-uuid', 'data-target', 'data-display-text'],
            img: [...(defaultSchema.attributes?.img || []), 'src', 'alt', 'title'],
        },
    };
    const markdownComponents = {
        span: ({ children, className, ...props }) => { // Holen uns die className
            const displayText = props['data-display-text'] ? decodeURIComponent(props['data-display-text']) : children;

            if (props['data-uuid']) {
                const uuid = props['data-uuid'];
                // Geben die Klasse weiter
                return <InternalLink uuid={uuid} displayText={displayText} className={className} />;
            }

            if (props['data-target']) {
                const targetTitle = decodeURIComponent(props['data-target']);
                // Geben die Klasse weiter
                return <InternalLink targetTitle={targetTitle} displayText={displayText} className={className} />;
            }

            return <span className={className} {...props}>{children}</span>;
        },

        // Die anderen Renderer bleiben wie gewohnt.
        img: (props) => <ResizableImage {...props} />,
        a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    };

    return (
        <div className="markdown-body">
            <ReactMarkdown
                remarkPlugins={[remarkGfm, wikiLinkPlugin]}
                rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
                components={markdownComponents}
                skipHtml={false}
            >
                {content || ''}
            </ReactMarkdown>
        </div>
    );
}
