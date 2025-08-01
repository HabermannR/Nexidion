import React from 'react';
import { Button, ButtonGroup, Dropdown } from 'react-bootstrap';
import { useContextStore  } from './contextStore'; // Der Store lebt im selben Feature-Ordner
import './ContextBar.css'; // Zugehörige Stile für die Komponente

/**
 * ContextBar ist eine in sich geschlossene Komponente zur Verwaltung der Node-Auswahl.
 * Sie zeigt den aktuellen Status an und bietet Aktionen zum Leeren, Speichern und Laden
 * von "Kontext-Sets". Sie ist vollständig vom globalen `zustand`-Store gesteuert.
 */
export default function ContextBar() {
    // Alle benötigten Zustände und Aktionen werden direkt aus dem Store geholt.
    // Die Komponente ist dadurch komplett "prop-less" und autonom.
    const {
        selectedNodeIds,
        savedSets,
        clearSelection,
        setSelection,
        saveCurrentSet,
        deleteSet
    } = useContextStore ();

    const handleSave = () => {
        const name = prompt("Name für diese Auswahl eingeben:");
        // Die Logik (Prüfungen, Speichern) ist im Store gekapselt.
        if (name) {
            saveCurrentSet(name);
        }
    };

    const handleLoad = (ids) => {
        setSelection(ids);
    };

    const handleDelete = (e, name) => {
        // Verhindert, dass der Klick auf den Löschen-Button auch das Laden auslöst.
        e.stopPropagation();
        if (window.confirm(`Soll das Kontext-Set "${name}" wirklich gelöscht werden?`)) {
            deleteSet(name);
        }
    };

    const hasSavedSets = Object.keys(savedSets).length > 0;

    return (
        <div className="context-bar">
            <span className="context-status-text">
                <strong>{selectedNodeIds.size}</strong> Node(s) als Kontext ausgewählt
            </span>

            <ButtonGroup>
                <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={clearSelection}
                    disabled={selectedNodeIds.size === 0}
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
                            disabled={selectedNodeIds.size === 0}
                        >
                            <i className="bx bx-save me-2"></i>Aktuelle Auswahl speichern...
                        </Dropdown.Item>

                        <Dropdown.Divider />
                        <Dropdown.Header>Gespeicherte Sets</Dropdown.Header>

                        {hasSavedSets ? (
                            Object.entries(savedSets).map(([name, ids]) => (
                                <Dropdown.Item
                                    key={name}
                                    className="context-set-item"
                                    onClick={() => handleLoad(ids)}
                                    title={`Set "${name}" laden`}
                                >
                                    <span className="context-set-name">
                                        {name} ({ids.length})
                                    </span>
                                    <Button
                                        variant="link"
                                        size="sm"
                                        className="text-danger p-0"
                                        onClick={(e) => handleDelete(e, name)}
                                        title={`Set "${name}" löschen`}
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