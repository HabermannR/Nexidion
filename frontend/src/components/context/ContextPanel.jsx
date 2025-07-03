// src/components/context/ContextPanel.jsx

import React, { useState, useEffect } from 'react';
import { useAppContext } from '../../context/AppContext';
import ListGroup from 'react-bootstrap/ListGroup';

// Import der neuen, sauberen Komponenten
import SelectionManager from './SelectionManager';
import ActionButtons from './ActionButtons';
import Chat from './Chat'; // Pfad anpassen, falls Chat.jsx woanders liegt

export default function ContextPanel({ onNodeUpdate }) {
  const { selectedNodeIds, getContextContent } = useAppContext();
  const [contextTitles, setContextTitles] = useState([]);

  // Holt die Titel der ausgewählten Nodes für die Anzeige
  useEffect(() => {
    const fetchTitles = async () => {
      if (selectedNodeIds.size > 0) {
        const { titles } = await getContextContent();
        setContextTitles(titles);
      } else {
        setContextTitles([]);
      }
    };
    fetchTitles();
  }, [selectedNodeIds, getContextContent]);

  return (
    // Ein Wrapper für das Padding der gesamten Spalte
    <div className="p-2"> 
      <SelectionManager />
      
      <hr />

      <div className="context-selection-list">
        <h5>Aktueller Kontext ({selectedNodeIds.size})</h5>
        {contextTitles.length > 0 ? (
          <ListGroup variant="flush" style={{ maxHeight: '150px', overflowY: 'auto' }}>
            {contextTitles.map((title, index) => <ListGroup.Item key={index} className="py-1 px-2 small">{title}</ListGroup.Item>)}
          </ListGroup>
        ) : (
          <p className="text-muted small">Wähle Nodes aus, um einen Kontext zu erstellen.</p>
        )}
      </div>

      <ActionButtons onNodeUpdate={onNodeUpdate} />
      
      <hr />

      <div className="chat-container" style={{ height: '90vh' }}>
        <Chat />
      </div>
    </div>
  );
}