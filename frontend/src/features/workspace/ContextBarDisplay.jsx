// src/features/workspace/ContextBarDisplay.jsx

import React from 'react';
import { Button, ButtonGroup, Dropdown } from 'react-bootstrap';
import './ContextBar.css';

export default function ContextBarDisplay({
    selectionSize,
    savedSets,
    onClear,
    onSave,
    onLoadSet,
    onDeleteSet,
    isExpanded,
    onToggleExpand,
    selectedNodes,
    onCopyContent,
    copyStatus,
}) {
    const handleSave = () => {
        const name = prompt('Name für diese Auswahl eingeben:');
        if (name) onSave(name);
    };

    const handleDelete = (e, name) => {
        e.stopPropagation();
        if (window.confirm(`Soll das Kontext-Set "${name}" wirklich gelöscht werden?`)) {
            onDeleteSet(name);
        }
    };

    const handleBarClick = (e) => {
        if (e.target.closest('button, .dropdown-menu')) return;
        if (selectionSize > 0) onToggleExpand();
    };

    const hasSavedSets = savedSets.length > 0;
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
                title={selectionSize > 0 ? 'Klicken zum Ein-/Ausklappen der Details' : ''}
            >
                <span className="context-status-text">
                    {selectionSize > 0 && <i className={`bx ${chevronIcon} me-1`}></i>}
                    <strong>{selectionSize}</strong> Node(s) als Kontext ausgewählt
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
                        title="Aktuelle Auswahl zurücksetzen"
                    >
                        <i className="bx bx-x"></i> Leeren
                    </Button>

                    <Dropdown as={ButtonGroup}>
                        <Dropdown.Toggle
                            split
                            variant="outline-secondary"
                            size="sm"
                            id="context-sets-dropdown"
                            title="Gespeicherte Kontext-Sets verwalten"
                        />
                        <Dropdown.Menu align="end">
                            <Dropdown.Item onClick={handleSave} disabled={selectionSize === 0}>
                                <i className="bx bx-save me-2"></i>Aktuelle Auswahl speichern...
                            </Dropdown.Item>
                            <Dropdown.Divider />
                            <Dropdown.Header>Gespeicherte Sets</Dropdown.Header>
                            {hasSavedSets ? (
                                savedSets.map((set) => (
                                    <Dropdown.Item
                                        key={set.name}
                                        className="context-set-item"
                                        onClick={() => onLoadSet(set.ids)}
                                        title={`Set "${set.name}" laden`}
                                    >
                                        <span className="context-set-name">
                                            {set.name} ({set.count})
                                        </span>
                                        <Button
                                            variant="link"
                                            size="sm"
                                            className="text-danger p-0"
                                            onClick={(e) => handleDelete(e, set.name)}
                                            title={`Set "${set.name}" löschen`}
                                        >
                                            <i className="bx bxs-trash"></i>
                                        </Button>
                                    </Dropdown.Item>
                                ))
                            ) : (
                                <Dropdown.ItemText>Noch keine Sets gespeichert.</Dropdown.ItemText>
                            )}
                        </Dropdown.Menu>
                    </Dropdown>
                </ButtonGroup>
            </div>

            {/* Expanded node list */}
            {isExpanded && selectionSize > 0 && (
                <div className="context-expanded-content">
                    <div className="context-expanded-list">
                        {selectedNodes.map(node => (
                            <div key={node.id} className="context-expanded-item" title={node.id}>
                                {node.title}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
