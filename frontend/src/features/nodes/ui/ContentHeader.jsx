// src/features/nodes/components/ContentHeader.jsx (ANGEPASST)

import React from 'react';
import {Button, ButtonGroup, Dropdown} from 'react-bootstrap';
import IconSelectorDropdown from './IconSelectorDropdown'; // Importieren
import './ContentHeader.css';

export default function ContentHeader({
                                          currentNode, // Wir brauchen den ganzen Node für das Icon
                                          vaultId,
                                          isEditing,
                                          onEditClick,
                                          onRenameClick,
                                          onDeleteClick,
                                      }) {
    return (
        <div className="content-header-container">
            {/* Icon-Selector links vom Titel */}
            {currentNode && vaultId && (
                <div className="me-2">
                    <IconSelectorDropdown currentNode={currentNode} vaultId={vaultId}/>
                </div>
            )}

            <h1 className="content-title mb-0">{currentNode?.title || 'Lädt...'}</h1>

            {!isEditing && (
                <div className="action-buttons">
                    <ButtonGroup>
                        <Button variant="primary" size="sm" onClick={onEditClick} title="Inhalt bearbeiten">
                            <i className="bx bx-pencil me-1"></i>
                            Bearbeiten
                        </Button>
                        <Dropdown as={ButtonGroup}>
                            <Dropdown.Toggle split variant="primary" size="sm" id="node-actions-dropdown"
                                             title="Weitere Aktionen"/>
                            <Dropdown.Menu align="end">
                                <Dropdown.Item onClick={onRenameClick}>
                                    <i className="bx bx-rename me-2"></i>
                                    Umbenennen...
                                </Dropdown.Item>
                                <Dropdown.Divider/>
                                <Dropdown.Item onClick={onDeleteClick} className="text-danger">
                                    <i className="bx bxs-trash me-2"></i>
                                    Löschen...
                                </Dropdown.Item>
                            </Dropdown.Menu>
                        </Dropdown>
                    </ButtonGroup>
                </div>
            )}
        </div>
    );
}