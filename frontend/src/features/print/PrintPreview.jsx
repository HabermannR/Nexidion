// src/features/print/PrintPreview.jsx

import React, { useEffect } from 'react';
import ReactDOM from 'react-dom';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import MarkdownRenderer from '../nodes/MarkdownRenderer.jsx';
import { Button } from 'react-bootstrap';
import './PrintPreview.css';

const PrintPreview = () => {
    // 1. Get state and actions directly from Zustand
    const printPreviewData = useWorkspaceStore(state => state.printPreviewData);
    const closePrintPreview = useWorkspaceStore(state => state.closePrintPreview);

    // 2. HOOKS MUST BE AT THE TOP (Before any early returns!)

    // Toggle the body class when the preview opens/closes
    useEffect(() => {
        // Only add the class if we actually have print data
        if (printPreviewData) {
            document.body.classList.add('print-preview-active');
        } else {
            document.body.classList.remove('print-preview-active');
        }

        // Cleanup on unmount
        return () => {
            document.body.classList.remove('print-preview-active');
        };
    }, [printPreviewData]); // Re-run this effect when printPreviewData changes

    // Handle keyboard shortcut (Escape to close)
    useEffect(() => {
        // Only attach listener if preview is active
        if (!printPreviewData) return;

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                closePrintPreview();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [printPreviewData, closePrintPreview]); // Dependencies

    // 3. NOW we can safely do our early return
    if (!printPreviewData) return null;

    const { nodes = [], toc = [] } = printPreviewData;

    // 4. Build the UI
    const previewContent = (
        <div className="print-preview-overlay">
            <div className="print-preview-container">

                {/* Header (Hidden during actual printing via CSS) */}
                <div className="print-preview-header d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom">
                    <h5 className="mb-0 text-muted">
                        <i className="bx bx-printer me-2"></i>
                        Print Preview ({nodes.length} document{nodes.length > 1 ? 's' : ''})
                    </h5>
                    <div>
                        <Button variant="primary" className="me-2" onClick={() => window.print()}>
                            <i className="bx bx-printer me-1"></i> Print (Ctrl+P)
                        </Button>
                        <Button variant="secondary" onClick={closePrintPreview}>
                            <i className="bx bx-x me-1"></i> Close
                        </Button>
                    </div>
                </div>

                {/* Table of Contents */}
                {toc && toc.length > 0 && (
                    <div className="print-toc mb-5">
                        <h2 className="mb-3">Table of Contents</h2>
                        <ul className="list-unstyled">
                            {toc.map(item => (
                                <li
                                    key={item.id}
                                    style={{ paddingLeft: `${item.level * 20}px`, marginBottom: '0.5rem' }}
                                >
                                    <a href={`#print-node-${item.id}`} className="text-decoration-none text-primary">
                                        {item.title}
                                    </a>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Nodes Content */}
                {nodes.map(node => (
                    <div key={node.id} id={`print-node-${node.id}`} className="print-node mb-5">
                        <h1 className="border-bottom pb-2 mb-4">{node.title}</h1>
                        <div className="view-content">
                            <MarkdownRenderer content={node.content || ''} />
                        </div>
                    </div>
                ))}

            </div>
        </div>
    );

    // 5. Mount it outside of the main #root
    return ReactDOM.createPortal(previewContent, document.body);
};

export default PrintPreview;