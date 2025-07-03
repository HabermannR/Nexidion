// src/components/context/SelectionManager.jsx

import React, { useState, useEffect, useCallback } from 'react';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import InputGroup from 'react-bootstrap/InputGroup';
import { useAppContext } from '../../context/AppContext';

const STORAGE_KEY = 'knowledgeBaseSelections';

export default function SelectionManager() {
  const { selectedNodeIds, setSelectedNodeIds } = useAppContext();
  
  const [savedSelections, setSavedSelections] = useState({});
  const [selectedName, setSelectedName] = useState('');

  // Lade gespeicherte Auswahlen beim ersten Rendern
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setSavedSelections(JSON.parse(stored));
      }
    } catch (error) {
      console.error("Could not load selections from localStorage", error);
    }
  }, []);

  const handleSave = useCallback(() => {
    if (selectedNodeIds.size === 0) {
      alert("Bitte Nodes auswählen, um die Auswahl zu speichern.");
      return;
    }
    const name = prompt("Name für diese Auswahl eingeben:");
    if (!name || !name.trim()) return;

    const newSelections = { ...savedSelections, [name.trim()]: Array.from(selectedNodeIds) };
    setSavedSelections(newSelections);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newSelections));
    alert(`Auswahl "${name.trim()}" gespeichert!`);
  }, [selectedNodeIds, savedSelections]);

  const handleLoad = useCallback(() => {
    if (!selectedName || !savedSelections[selectedName]) return;
    const idsToLoad = savedSelections[selectedName];
    setSelectedNodeIds(new Set(idsToLoad));
  }, [selectedName, savedSelections, setSelectedNodeIds]);

  const handleDelete = useCallback(() => {
    if (!selectedName || !savedSelections[selectedName]) return;
    if (window.confirm(`Soll die Auswahl "${selectedName}" wirklich gelöscht werden?`)) {
      const newSelections = { ...savedSelections };
      delete newSelections[selectedName];
      setSavedSelections(newSelections);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newSelections));
      setSelectedName(''); // Dropdown zurücksetzen
    }
  }, [selectedName, savedSelections]);

  return (
    <div className="selection-manager">
      <h5>Auswahlen verwalten</h5>
      <InputGroup size="sm" className="mb-2">
        <Form.Select value={selectedName} onChange={(e) => setSelectedName(e.target.value)}>
          <option value="">-- Gespeicherte Auswahl laden --</option>
          {Object.keys(savedSelections).sort().map(name => (
            <option key={name} value={name}>{name}</option>
          ))}
        </Form.Select>
        <Button variant="outline-primary" onClick={handleLoad} disabled={!selectedName}>Laden</Button>
        <Button variant="outline-danger" onClick={handleDelete} disabled={!selectedName}>Löschen</Button>
      </InputGroup>
      <div className="d-grid">
        <Button variant="secondary" size="sm" onClick={handleSave} disabled={selectedNodeIds.size === 0}>
          Aktuelle Auswahl speichern
        </Button>
      </div>
    </div>
  );
}