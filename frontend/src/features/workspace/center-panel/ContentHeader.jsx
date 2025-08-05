// src/features/workspace/center-panel/ContentHeader.jsx
import React from 'react';
import { Button, ButtonGroup, Dropdown } from 'react-bootstrap';
import IconSelectorDropdown from './IconSelectorDropdown.jsx'; // Pfad prüfen
import './ContentHeader.css';

export default function ContentHeader({
                                          currentVersion,
                                          vaultId,
                                          isEditing,
                                          onEditClick,
                                          onRenameClick,
                                          onDeleteClick,
                                      }) {
    if (!currentVersion) {
        return <div className="content-header-container"><h1>Lädt...</h1></div>;
    }

    return (
        <div className="content-header-container">
            <div className="me-2">
                {/* Wir übergeben alle nötigen Props an den Icon-Selector */}
                <IconSelectorDropdown
                    currentVersion={currentVersion}
                    vaultId={vaultId}
                    nodeId={currentVersion.node_id} // Die nodeId ist Teil des Versionsobjekts
                />
            </div>

            <h1 className="content-title mb-0">{currentVersion.title}</h1>

            {!isEditing && (
                <div className="action-buttons">
                    <ButtonGroup>
                        <Button variant="primary" size="sm" onClick={onEditClick} title="Inhalt bearbeiten">
                            <i className="bx bx-pencil me-1"></i>
                        </Button>
                        <Dropdown as={ButtonGroup}>
                            <Dropdown.Toggle split variant="primary" size="sm" id="node-actions-dropdown" title="Weitere Aktionen" />
                            <Dropdown.Menu align="end">
                                <Dropdown.Item onClick={onRenameClick}>
                                    <i className="bx bx-rename me-2"></i> Umbenennen...
                                </Dropdown.Item>
                                <Dropdown.Divider />
                                <Dropdown.Item onClick={onDeleteClick} className="text-danger">
                                    <i className="bx bxs-trash me-2"></i> Löschen...
                                </Dropdown.Item>
                            </Dropdown.Menu>
                        </Dropdown>
                    </ButtonGroup>
                </div>
            )}
        </div>
    );
}