// src/components/common/DeleteNodeModal.jsx

import React from 'react';
import Modal from 'react-bootstrap/Modal';
import Button from 'react-bootstrap/Button';

export default function DeleteNodeModal({ node, onConfirm, onCancel }) {
  // Zeigt nichts an, wenn es nicht gebraucht wird.
  // Das ist redundant, da NodesView es eh nur rendert, wenn `node` existiert, aber es ist eine gute Absicherung.
  if (!node) {
    return null;
  }

  return (
    // 'show' ist hier immer true, weil die Komponente nur gerendert wird, wenn sie sichtbar sein soll.
    // 'onHide' wird mit onCancel verknüpft, damit das Modal auch bei Klick daneben oder auf ESC schließt.
    <Modal show={true} onHide={onCancel} centered>
      <Modal.Header closeButton>
        <Modal.Title as="h2">Löschen bestätigen</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <p>
          Bist du sicher, dass du den Node "<strong>{node.title}</strong>" löschen möchtest?
        </p>
        <p className="text-danger">
          Diese Aktion kann nicht rückgängig gemacht werden.
        </p>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button variant="danger" onClick={onConfirm}>
          Endgültig löschen
        </Button>
      </Modal.Footer>
    </Modal>
  );
}