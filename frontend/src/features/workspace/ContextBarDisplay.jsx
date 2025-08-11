// src/features/workspace/ContextBarDisplay.jsx

import React from 'react';
import { Button, ButtonGroup, Dropdown } from 'react-bootstrap';
import './ContextBar.css';

/**
 * A "dumb" presentational component for the context bar.
 * It now handles rendering an expanded view showing the titles of selected nodes.
 */
export default function ContextBarDisplay({
                                              selectionSize,
                                              savedSets,
                                              onClear,
                                              onSave,
                                              onLoadSet,
                                              onDeleteSet,
                                              // NEW PROPS for the expandable detail view
                                              isExpanded,
                                              onToggleExpand,
                                              selectedNodes
                                          }) {

    const handleSave = () => {
        const name = prompt("Name für diese Auswahl eingeben:");
        if (name) {
            onSave(name);
        }
    };

    const handleDelete = (e, name) => {
        e.stopPropagation();
        if (window.confirm(`Soll das Kontext-Set "${name}" wirklich gelöscht werden?`)) {
            onDeleteSet(name);
        }
    };

    // Clicking anywhere on the bar (except buttons) should toggle the view,
    // but only if there's something to show.
    const handleBarClick = (e) => {
        // Prevent toggling if a button inside the bar was clicked
        if (e.target.closest('button, .dropdown-menu')) {
            return;
        }
        if (selectionSize > 0) {
            onToggleExpand();
        }
    };

    const hasSavedSets = savedSets.length > 0;

    // Determine the chevron icon based on the expanded state
    const chevronIcon = isExpanded ? 'bxs-chevron-down' : 'bxs-chevron-right';

    return (
        <div className="context-bar-wrapper">
            <div
                className={`context-bar ${selectionSize > 0 ? 'expandable' : ''}`}
                onClick={handleBarClick}
                title={selectionSize > 0 ? "Klicken zum Ein-/Ausklappen der Details" : ""}
            >
                <span className="context-status-text">
                    {/* Add the chevron icon for visual feedback */}
                    {selectionSize > 0 && <i className={`bx ${chevronIcon} me-1`}></i>}
                    <strong>{selectionSize}</strong> Node(s) als Kontext ausgewählt
                </span>

                <ButtonGroup>
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
                            <Dropdown.Item
                                onClick={handleSave}
                                disabled={selectionSize === 0}
                            >
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
                                <Dropdown.ItemText>
                                    Noch keine Sets gespeichert.
                                </Dropdown.ItemText>
                            )}
                        </Dropdown.Menu>
                    </Dropdown>
                </ButtonGroup>
            </div>

            {/* CONDITIONAL RENDERING: Show this div only when expanded and items exist */}
            {isExpanded && selectionSize > 0 && (
                <div className="context-expanded-content">
                    <div className="context-expanded-list">
                        {selectedNodes.map(node => (
                            <div key={node.id} className="context-expanded-item" title={node.title}>
                                {node.title}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}