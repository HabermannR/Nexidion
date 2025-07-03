import React, { useRef } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { useAppContext } from '../../context/AppContext';

/**
 * Stellt einen einzelnen, interaktiven Node im ProjectTree dar.
 * Beinhaltet Drag-and-Drop, Checkboxen für die Auswahl und Steuerelemente.
 */
function TreeNode({ node, onNodeClick, onAddNode, onDeleteNode, onMoveNode, children }) {
  const ref = useRef(null);
  const { selectedNodeIds, toggleNodeSelection } = useAppContext();
  const { collapsedNodes, toggleNodeCollapse } = useAppContext(); // Holen wir uns direkt aus dem Kontext

  const [{ isDragging }, drag] = useDrag({
    type: 'NODE',
    item: () => ({ id: node.id, parentId: node.parentId }), // Nur die IDs mitgeben
    collect: (monitor) => ({ isDragging: monitor.isDragging() }),
  });

  const [, drop] = useDrop({
    accept: 'NODE',
    drop: (item) => {
      if (item.id !== node.id && item.parentId !== node.id) {
        onMoveNode(item, node); // item enthält { id, parentId }
      }
    },
  });

  drag(drop(ref));
  const isCollapsed = collapsedNodes.has(node.id);

  // Dynamische Klassen für das Styling
  const nodeClasses = [
    'tree-node',
    selectedNodeIds.has(node.id) ? 'is-selected' : '',
    node.children && node.children.length > 0 ? 'has-children' : '',
    !isCollapsed ? 'is-expanded' : ''
  ].join(' ');

   return (
    <div ref={ref} className="tree-node-wrapper" style={{ opacity: isDragging ? 0.4 : 1 }}>
      <div className={nodeClasses}>
        <div className="tree-node-content" onClick={() => onNodeClick(node)}>
          <span className="collapse-icon" onClick={(e) => {
              e.stopPropagation();
              if (node.children && node.children.length > 0) {
                  toggleNodeCollapse(node.id);
              }
          }}>
             {node.children && node.children.length > 0 && (isCollapsed ? '▶' : '▼')}
          </span>
          <input
            type="checkbox"
            className="node-checkbox"
            checked={selectedNodeIds.has(node.id)}
            onChange={(e) => { e.stopPropagation(); toggleNodeSelection(node.id); }}
            onClick={(e) => e.stopPropagation()}
          />
          <span className="node-title">{node.title}</span>
        </div>
        
        <div className="node-controls">
          <button 
            className="control-btn control-btn-add" 
            onClick={(e) => { e.stopPropagation(); onAddNode(node.id); }}
            aria-label={`Add child to ${node.title}`}
          >
            +
          </button>
          <button 
            className="control-btn control-btn-delete" 
            onClick={(e) => { e.stopPropagation(); onDeleteNode(node); }}
            aria-label={`Delete ${node.title}`}
          >
            -
          </button>
        </div>

      </div>

      {!isCollapsed && children && (
        <div className="tree-node-children">
          {children}
        </div>
      )}
    </div>
  );
}

export default TreeNode;