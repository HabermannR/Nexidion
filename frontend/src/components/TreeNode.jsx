import React, { useRef } from 'react'
import { useDrag, useDrop } from 'react-dnd'
import TreeView from 'react-treeview'

const TreeNode = ({ node, path, index, moveNode, handleNodeClick, handleAddNode, handleDeleteNode }) => {
  const ref = useRef(null)

  const [{ isDragging }, drag] = useDrag({
    type: 'NODE',
    item: () => ({ 
      index, 
      path, 
      title: node.title,
      sourceParentPath: path.split('/').slice(0, -1).join('/')
    }),
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  })

  const [, drop] = useDrop({
    accept: 'NODE',
    hover(item, monitor) {
      if (!ref.current) {
        return
      }
      // We don't need to do anything in hover for this case
    },
    drop(item, monitor) {
      const sourcePath = item.path
      const targetPath = path
      // Check if this is the actual drop target (not a parent)
      if (!monitor.didDrop() && sourcePath !== targetPath) {
        console.log('Source Path:', sourcePath)
        console.log('Target Path:', targetPath)
        moveNode(sourcePath, targetPath)
        return { moved: true }
      }
    },
    collect: (monitor) => ({
      isOver: monitor.isOver({ shallow: true }),
      canDrop: monitor.canDrop(),
    }),
  })

  const PlusMinusIcon = ({ onAdd, onDelete, isSummary }) => (
    <span className="plus-minus-icon">
      <span 
        className="plus-icon"
        onClick={(e) => {
          e.stopPropagation()
          onAdd()
        }}
      >
        +
      </span>
      {!isSummary && (
        <span 
          className="minus-icon"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
        >
          -
        </span>
      )}
    </span>
  )

  drag(drop(ref))

  const isSummary = node.title === 'Summary' && path === 'Summary'

  return (
    <div ref={ref} style={{ cursor: 'move', opacity: isDragging ? 0.5 : 1 }}>
      <TreeView
        nodeLabel={
          <div className="node-label">
            <span 
              className={path === window.location.pathname.split('/nodes/')[1] ? 'active-node' : ''}
              onClick={() => handleNodeClick(path)}
            >
              {node.title}
            </span>
            <PlusMinusIcon
              onAdd={() => handleAddNode(path)}
              onDelete={() => handleDeleteNode(path)}
              isSummary={isSummary}
            />
          </div>
        }
        defaultCollapsed={false}
      >
        {node.children && node.children.length > 0 && 
          node.children.map((childNode, childIndex) => (
            <TreeNode
              key={`${path}/${childNode.title}`}
              node={childNode}
              path={`${path}/${childNode.title}`}
              index={childIndex}
              moveNode={moveNode}
              handleNodeClick={handleNodeClick}
              handleAddNode={handleAddNode}
              handleDeleteNode={handleDeleteNode}
            />
          ))
        }
      </TreeView>
    </div>
  )
}

export default TreeNode