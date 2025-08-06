// src/features/workspace/left-panel/ContextBarDisplay.jsx (NEW FILE)

import React from 'react';
import { Button, ButtonGroup, Dropdown } from 'react-bootstrap';
import './ContextBar.css';

/**
 * A "dumb" presentational component for the context bar.
 * It has no knowledge of Zustand and receives all its data and functions as props.
 * This makes it safe to be rendered multiple times.
 */
export default function ContextBarDisplay({
                                              selectionSize,
                                              savedSets, // This is now our array: [{name, count, ids}, ...]
                                              onClear,
                                              onSave,
                                              onLoadSet,
                                              onDeleteSet
                                          }) {

    const handleSave = () => {
        const name = prompt("Name für diese Auswahl eingeben:");
        if (name) {
            onSave(name); // Call the function from props
        }
    };

    const handleDelete = (e, name) => {
        e.stopPropagation();
        if (window.confirm(`Soll das Kontext-Set "${name}" wirklich gelöscht werden?`)) {
            onDeleteSet(name); // Call the function from props
        }
    };

    const hasSavedSets = Object.keys(savedSets).length > 0;

    return (
        <div className="context-bar">
            <span className="context-status-text">
                <strong>{selectionSize}</strong> Node(s) als Kontext ausgewählt
            </span>

            <ButtonGroup>
                <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={onClear} // Call the function from props
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
                            // MAP OVER THE ARRAY DIRECTLY
                            savedSets.map((set) => (
                                <Dropdown.Item
                                    key={set.name}
                                    className="context-set-item"
                                    onClick={() => onLoadSet(set.ids)} // Use the ids property
                                    title={`Set "${set.name}" laden`}
                                >
                                    <span className="context-set-name">
                                        {set.name} ({set.count}) {/* Use the name and count properties */}
                                    </span>
                                    <Button
                                        variant="link"
                                        size="sm"
                                        className="text-danger p-0"
                                        onClick={(e) => handleDelete(e, set.name)} // Use the name property
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
    );
}