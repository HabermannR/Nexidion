// src/features/nodes/components/ContentHeader.jsx

import React from "react";
import { Button, ButtonGroup, Dropdown } from "react-bootstrap";
import "./ContentHeader.css";

/**
 * Zeigt den Header des Inhaltsbereichs an.
 * Enthält den Titel des Nodes sowie Aktionen zum Bearbeiten, Umbenennen und Löschen.
 * Die Komponente ist "dumm" und erhält alle Daten und Handler als Props.
 */
export default function ContentHeader({
  title,
  isEditing,
  onEditClick,
  onRenameClick,
  onDeleteClick,
}) {
  return (
    <div className="content-header-container">
      <h1 className="content-title mb-0">{title}</h1>

      {/* Die Action-Buttons werden nur angezeigt, wenn wir NICHT im Edit-Modus sind. */}
      {!isEditing && (
        <div className="action-buttons">
          <ButtonGroup>
            {/* 1. Der Haupt-Button zum Starten des Edit-Modus */}
            <Button
              variant="primary"
              size="sm"
              onClick={onEditClick}
              title="Inhalt bearbeiten"
            >
              <i className="bx bx-pencil me-1"></i>
              Bearbeiten
            </Button>

            {/* 2. Das Dropdown für weitere Aktionen */}
            <Dropdown as={ButtonGroup}>
              <Dropdown.Toggle
                split
                variant="primary"
                size="sm"
                id="node-actions-dropdown"
                title="Weitere Aktionen"
              />
              <Dropdown.Menu align="end">
                <Dropdown.Item onClick={onRenameClick}>
                  <i className="bx bx-rename me-2"></i>
                  Umbenennen...
                </Dropdown.Item>
                <Dropdown.Divider />
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
