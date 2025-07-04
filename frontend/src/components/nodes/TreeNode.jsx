import React, { useRef } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { useAppContext } from '../../context/AppContext';

function TreeNode({ node, onNodeClick, onAddNode, onDeleteNode, onMoveNode, children }) {
  const ref = useRef(null);
  const { selectedNodeIds, toggleNodeSelection, collapsedNodes, toggleNodeCollapse } = useAppContext();
  
  const [{ isDragging }, drag] = useDrag({
    type: 'NODE',
    item: () => {
      const dragItem = { 
        id: node.id, 
        parentId: node.parent_id,
        title: node.title 
      };
      return dragItem;
    },
    collect: (monitor) => ({ 
      isDragging: monitor.isDragging() 
    }),
    canDrag: () => true,
  });
  
  const [{ isOver, isOverShallow, canDrop }, drop] = useDrop({
    accept: 'NODE',
    drop: (item, monitor) => {
      if (!monitor.isOver({ shallow: true })) {
        return;
      }
      
      if (item.id !== node.id && item.parentId !== node.id) {
        onMoveNode(item, node);
        return { moved: true };
      } else {
        return { moved: false };
      }
    },
    collect: (monitor) => ({
      isOver: monitor.isOver(),
      isOverShallow: monitor.isOver({ shallow: true }),
      canDrop: monitor.canDrop(),
    }),
    canDrop: (item) => {
      const canDropResult = item.id !== node.id && item.parentId !== node.id;
      return canDropResult;
    },
  });
  
  drag(drop(ref));
  
  const isCollapsed = collapsedNodes.has(node.id);
  
  const nodeClasses = [
    'tree-node',
    selectedNodeIds.has(node.id) ? 'is-selected' : '',
    node.children && node.children.length > 0 ? 'has-children' : '',
    !isCollapsed ? 'is-expanded' : '',
    isOverShallow && canDrop ? 'drag-over-valid' : '',
    isOverShallow && !canDrop ? 'drag-over-invalid' : ''
  ].join(' ');
  
  return (
    <div 
      ref={ref} 
      className="tree-node-wrapper" 
      style={{ 
        opacity: isDragging ? 0.4 : 1,
        cursor: isDragging ? 'grabbing' : 'grab',
        backgroundColor: isOverShallow && canDrop ? '#e8f5e8' : 
                         isOverShallow && !canDrop ? '#ffe8e8' : 'transparent',
        border: isOverShallow && canDrop ? '2px dashed #4caf50' : 
                isOverShallow && !canDrop ? '2px dashed #f44336' : '2px solid transparent',
        transition: 'all 0.2s ease'
      }}
    >
      <div className={nodeClasses}>
        <div className="tree-node-content" onClick={() => onNodeClick(node)}>
          <span 
            className="collapse-icon" 
            onClick={(e) => {
              e.stopPropagation();
              if (node.children && node.children.length > 0) {
                toggleNodeCollapse(node.id);
              }
            }}
          >
            {node.children && node.children.length > 0 && (isCollapsed ? '▶' : '▼')}
          </span>
          
          <input
            type="checkbox"
            className="node-checkbox"
            checked={selectedNodeIds.has(node.id)}
            onChange={(e) => { 
              e.stopPropagation(); 
              toggleNodeSelection(node.id); 
            }}
            onClick={(e) => e.stopPropagation()}
          />
          
          <span className="node-title">{node.title}</span>
        </div>
        
        <div className="node-controls">
          <button 
            className="control-btn control-btn-add" 
            onClick={(e) => { 
              e.stopPropagation(); 
              onAddNode(node.id); 
            }}
            aria-label={`Add child to ${node.title}`}
          >
            +
          </button>
          <button 
            className="control-btn control-btn-delete" 
            onClick={(e) => { 
              e.stopPropagation(); 
              onDeleteNode(node); 
            }}
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