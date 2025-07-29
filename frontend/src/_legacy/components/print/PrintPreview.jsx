import React, { useEffect } from 'react';
import ReactDOM from 'react-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAppContext } from '../../context/AppContext';
import { renderTextWithLinks } from '../../utils/textUtils';
import SecureImage from '../common/SecureImage';

const PrintPreview = ({ onLinkClick }) => {
    const { printPreviewData, exitPrintPreview } = useAppContext();
    const { nodes, toc } = printPreviewData || { nodes: [], toc: [] };


    // This effect adds a class to the body when the preview is active,
    // allowing global styles to hide the main app and show the print view.
    // It cleans up by removing the class when the component unmounts.
    useEffect(() => {
        document.body.classList.add('print-preview-active');

        // Cleanup function: remove the class when the component unmounts
        return () => {
            document.body.classList.remove('print-preview-active');
        };
    }, []); // Empty dependency array ensures this runs only on mount and unmount

    const previewContent = (
        <div className="print-preview-overlay">
            <div className="print-preview-container">
                <div className="print-preview-header">
                    <p>Print Preview ({nodes.length} nodes)</p>
                    <div>
                        <button className="btn btn-primary" onClick={() => window.print()}>
                            Print (Ctrl+P)
                        </button>
                        <button className="btn btn-secondary" onClick={exitPrintPreview}>
                            Exit Preview
                        </button>
                    </div>
                </div>

                {toc && toc.length > 0 && (
                    <div className="print-toc">
                        <h2>Inhaltsverzeichnis</h2>
                        <ul>
                            {toc.map(item => (
                                <li
                                    key={item.id}
                                    style={{ paddingLeft: `${item.level * 20}px` }}
                                >
                                    <a href={`#print-node-${item.id}`}>{item.title}</a>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {nodes.map(node => (
                    <div key={node.id} id={`print-node-${node.id}`} className="print-node">
                        <h1>{node.title}</h1>
                        <div className="view-content">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                    p: ({ node, ...props }) => (
                                        <p {...props}>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </p>
                                    ),
                                    li: ({ node, ...props }) => (
                                        <li {...props}>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </li>
                                    ),
                                    h1: ({ node, ...props }) => (
                                        <h1 {...props}>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </h1>
                                    ),
                                    h2: ({ node, ...props }) => (
                                        <h2>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </h2>
                                    ),
                                    h3: ({ node, ...props }) => (
                                        <h3>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </h3>
                                    ),
                                    h4: ({ node, ...props }) => (
                                        <h4>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </h4>
                                    ),
                                    h5: ({ node, ...props }) => (
                                        <h5>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </h5>
                                    ),
                                    h6: ({ node, ...props }) => (
                                        <h6>
                                            {renderTextWithLinks(props.children, onLinkClick)}
                                        </h6>
                                    ),
                                    img: SecureImage,
                                }}
                            >
                                {node.content || ''}
                            </ReactMarkdown>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );

    return ReactDOM.createPortal(previewContent, document.body);
};

export default PrintPreview;
