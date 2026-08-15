// src/features/workspace/ContextBarDisplay.jsx

import React from 'react';
import { Button, ButtonGroup } from 'react-bootstrap';
import './ContextBar.css';

export default function ContextBarDisplay({
    selectionSize,
    onClear,
    onRemoveNode,
    isExpanded,
    onToggleExpand,
    selectedNodes,
    onCopyContent,
    copyStatus,
}) {
    const handleBarClick = (e) => {
        if (e.target.closest('button')) return;
        if (selectionSize > 0) onToggleExpand();
    };

    const chevronIcon = isExpanded ? 'bxs-chevron-down' : 'bxs-chevron-right';

    const copyLabel = () => {
        if (copyStatus === 'copying') return '…';
        if (copyStatus === 'success') return '✓';
        if (copyStatus === 'error') return '✗';
        return '⎘';
    };

    return (
        <div className="context-bar-wrapper">
            <div
                className={`context-bar ${selectionSize > 0 ? 'expandable' : ''}`}
                onClick={handleBarClick}
                title={selectionSize > 0 ? 'Click to expand/collapse details' : ''}
            >
                <span className="context-status-text">
                    {selectionSize > 0 && <i className={`bx ${chevronIcon} me-1`}></i>}
                    <strong>{selectionSize}</strong> node(s) selected as context
                </span>

                <ButtonGroup>
                    {/* Copy content button — lives here now */}
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={onCopyContent}
                        disabled={selectionSize === 0 || copyStatus === 'copying'}
                        title={
                            copyStatus === 'success' ? 'Copied!'
                            : copyStatus === 'error' ? 'Copy failed'
                            : `Copy content of ${selectionSize} node(s)`
                        }
                        style={{ minWidth: '2rem' }}
                    >
                        {copyLabel()}
                    </Button>

                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={onClear}
                        disabled={selectionSize === 0}
                        title="Clear current selection"
                    >
                        <i className="bx bx-x"></i> Clear
                    </Button>

                </ButtonGroup>
            </div>

            {/* Expanded node list */}
            {isExpanded && selectionSize > 0 && (
                <div className="context-expanded-content">
                    <div className="context-expanded-list">
                        {selectedNodes.map(node => (
                            <div key={node.id} className="context-expanded-item" title={node.id}>
                                <button
                                    type="button"
                                    className="context-expanded-remove"
                                    onClick={() => onRemoveNode(node.id)}
                                    title={`Remove ${node.title} from context`}
                                    aria-label={`Remove ${node.title} from context`}
                                >
                                    <i className="bx bx-x" aria-hidden="true"></i>
                                </button>
                                <span className="context-expanded-title">{node.title}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
