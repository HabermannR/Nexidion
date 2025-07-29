// src/components/context/SelectionManager.jsx

import React, { useState, useEffect, useCallback } from 'react';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import InputGroup from 'react-bootstrap/InputGroup';
import { useAppContext } from '../../context/AppContext';

// Der Key bleibt gleich, die Struktur innen drin ändert sich
const STORAGE_KEY = 'knowledgeBaseSelections';

export default function SelectionManager() {
  // Holen uns den aktiven Vault aus dem Context.
  const { selectedNodeIds, setSelectedNodeIds, activeVault, clearNodeSelection  } = useAppContext();
  
  // Dieser State hält jetzt ALLE Auswahlen für ALLE Vaults
  const [allSavedSelections, setAllSavedSelections] = useState({});
  const [selectedName, setSelectedName] = useState('');

  // Lade alle Auswahlen beim ersten Rendern
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setAllSavedSelections(JSON.parse(stored));
      }
    } catch (error) {
      console.error("Could not load selections from localStorage", error);
    }
  }, []);

  // Hilfsfunktion, um die Auswahlen NUR für den aktuellen Vault zu bekommen
  const getSelectionsForCurrentVault = useCallback(() => {
    if (!activeVault) return {};
    return allSavedSelections[`vault-${activeVault.id}`] || {};
  }, [allSavedSelections, activeVault]);


  const handleSave = useCallback(() => {
    if (!activeVault) return; // Sicherheitscheck
    if (selectedNodeIds.size === 0) {
      alert("Bitte Nodes auswählen, um die Auswahl zu speichern.");
      return;
    }
    const name = prompt("Name für diese Auswahl eingeben:");
    if (!name || !name.trim()) return;

    const vaultKey = `vault-${activeVault.id}`;
    const newSelectionsForVault = {
        ...getSelectionsForCurrentVault(),
        [name.trim()]: Array.from(selectedNodeIds)
    };
    
    const updatedAllSelections = {
        ...allSavedSelections,
        [vaultKey]: newSelectionsForVault
    };

    setAllSavedSelections(updatedAllSelections);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedAllSelections));
    alert(`Auswahl "${name.trim()}" gespeichert!`);

  }, [selectedNodeIds, activeVault, allSavedSelections, getSelectionsForCurrentVault]);

  const handleLoad = useCallback(() => {
    if (!activeVault || !selectedName) return;

    const selectionsForVault = getSelectionsForCurrentVault();
    const idsToLoad = selectionsForVault[selectedName];

    if (idsToLoad) {
      setSelectedNodeIds(new Set(idsToLoad));
    }
  }, [selectedName, activeVault, getSelectionsForCurrentVault, setSelectedNodeIds]);

  const handleDelete = useCallback(() => {
    if (!activeVault || !selectedName) return;
    
    if (window.confirm(`Soll die Auswahl "${selectedName}" wirklich gelöscht werden?`)) {
        const vaultKey = `vault-${activeVault.id}`;
        const selectionsForVault = { ...getSelectionsForCurrentVault() };
        delete selectionsForVault[selectedName];

        const updatedAllSelections = {
            ...allSavedSelections,
            [vaultKey]: selectionsForVault
        };

        setAllSavedSelections(updatedAllSelections);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updatedAllSelections));
        setSelectedName(''); // Dropdown zurücksetzen
    }
  }, [selectedName, activeVault, allSavedSelections, getSelectionsForCurrentVault]);

  // Zeige im Dropdown nur die Auswahlen für den aktuellen Vault an
  const currentVaultSelections = getSelectionsForCurrentVault();

  // Wenn kein Vault aktiv ist, wird die Komponente quasi deaktiviert
  if (!activeVault) {
      return (
        <div className="selection-manager text-muted small">
            <h5 className="text-muted">Auswahlen verwalten</h5>
            Bitte einen Vault auswählen, um Auswahlen zu verwalten.
        </div>
      );
  }

  return (
    <div className="selection-manager mt-3">
      <h5 className="mb-2">Auswahlen verwalten</h5>
      <InputGroup size="sm" className="mb-2">
        <Form.Select 
            value={selectedName} 
            onChange={(e) => setSelectedName(e.target.value)}
            disabled={Object.keys(currentVaultSelections).length === 0}
        >
          <option value="">-- Gespeicherte Auswahl laden --</option>
          {Object.keys(currentVaultSelections).sort().map(name => (
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
		<Button 
            variant="tertiary" // oder "outline-danger"
            size="sm" 
            onClick={clearNodeSelection} 
            disabled={selectedNodeIds.size === 0}
        >
            Aktuelle Auswahl leeren ({selectedNodeIds.size})
        </Button>
      </div>
    </div>
  );
}