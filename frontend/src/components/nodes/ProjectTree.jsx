// src/components/nodes/ProjectTree.jsx (ANGEPASSTE VERSION)

import React from 'react';
import TreeNode from './TreeNode';
import './ProjectTree.css'; 

/**
 * ProjectTree ist der Container für die gesamte Baumansicht.
 * Er rendert die Baumstruktur rekursiv mithilfe der TreeNode-Komponente
 * und stellt die von der CSS erwartete Klassenstruktur bereit.
 */
export default function ProjectTree({ 
  treeData, 
  activeNodeId,
  onNodeClick, 
  onAddNode, 
  onDeleteNode, 
  onMoveNode 
}) {
  
  const renderTree = (nodes) => {
    if (!nodes || nodes.length === 0) {
      return null;
    }
    return nodes.map(node => (
      <TreeNode
        key={node.id}
        node={node}
        // Props werden einfach weitergereicht
        onNodeClick={onNodeClick}
        onAddNode={onAddNode}
        onDeleteNode={onDeleteNode}
        onMoveNode={onMoveNode}
      >
        {/* Rekursion für die Kind-Elemente */}
        {renderTree(node.children)}
      </TreeNode>
    ));
  };

  return (
    // KORREKTUR 1: Der äußere Container bekommt die von der CSS erwartete Klasse.
    // Dieser Container wird die volle Höhe einnehmen (dank Flexbox in der CSS).
    <div className="project-tree-container">
      
      {/* Da du keine Suche wolltest, lassen wir die .tree-search-bar weg. */}
      
      {/* KORREKTUR 2: Wir fügen den .tree-node-list-Wrapper hinzu. */}
      {/* Dieser Container wird scrollbar sein, wenn der Inhalt zu lang ist. */}
      <div className="tree-node-list">
        {treeData && treeData.length > 0 ? (
          renderTree(treeData)
        ) : (
          <div className="p-3 text-center text-muted">
            <p>Kein Projekt geladen.</p>
            <button 
              className="btn btn-primary btn-sm" 
              onClick={() => onAddNode(null)} // onAddNode(null) für einen Wurzel-Node
            >
              Ersten Node erstellen
            </button>
          </div>
        )}
      </div>
    </div>
  );
}