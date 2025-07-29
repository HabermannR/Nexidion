import React from 'react';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';

export default function NodeEditor({ isEditing, content, onContentChange, onSave, onCancel, renderViewMode }) {
  if (isEditing) {
    return (
      <div className="p-3">
        <Form.Control 
          as="textarea" 
          value={content} 
          onChange={(e) => onContentChange(e.target.value)} 
          rows={30}
          className="mb-2"
        />
        <div className="d-flex gap-2">
          <Button variant="primary" onClick={onSave}>Speichern</Button>
          <Button variant="outline-secondary" onClick={onCancel}>Abbrechen</Button>
        </div>
      </div>
    );
  }

  // Im Ansichtsmodus rufen wir die übergebene Render-Funktion auf
  return renderViewMode(content);
}