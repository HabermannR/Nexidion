// src/features/workspace/left-panel/ProjectTree.jsx

import React, { useCallback, useRef, useEffect } from "react";
import { NavLink, useParams, useNavigate } from "react-router-dom";
import { useDrag, useDrop } from "react-dnd";
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import apiClient from "../../api/apiClient.js";
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import "./ProjectTree.css";

const ItemTypes = { NODE: "NODE" };

const useVaultTreeQuery = (vaultId) => {
    return useQuery({
        queryKey: ['vaultTree', vaultId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/?format=tree`).then(res => res.data),
        enabled: !!vaultId,
    });
};

// ============================================================================
// TreeNode Komponente
// ============================================================================
const TreeNode = React.memo(({ node, onAddNode, onMoveNode, onNodeClick, highlightedNodeIds = new Set() }) => {
    const { vaultId } = useParams();
    const wrapperRef = useRef(null);
    const dropRef = useRef(null);

    const { collapsedNodes, toggleNodeCollapse, selectedNodeIds, toggleNodeSelection } = useWorkspaceStore();
    const isSelected = selectedNodeIds.has(node.id);
    const isExpanded = !collapsedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    
    // Prüfe ob dieser Node von der Suche getroffen wurde
    const isHighlighted = highlightedNodeIds.has(node.id);

    const [{isDragging}, drag] = useDrag(() => ({
        type: ItemTypes.NODE,
        item: { id: node.id, parent_id: node.parent_id },
        collect: (monitor) => ({ isDragging: !!monitor.isDragging() }),
    }));

    const [{isOver, canDrop}, drop] = useDrop(() => ({
        accept: ItemTypes.NODE,
        canDrop: (draggedItem) =>
            draggedItem.id !== node.id && draggedItem.parent_id !== node.id,
        drop: (draggedItem) => onMoveNode(draggedItem, node),
        collect: (monitor) => ({
            isOver: !!monitor.isOver(),
            canDrop: !!monitor.canDrop(),
        }),
    }));

    drag(wrapperRef);
    drop(dropRef);

    const handleToggleExpand = (e) => {
        e.stopPropagation(); e.preventDefault();
        if (hasChildren) toggleNodeCollapse(node.id);
    };
    const handleSelectNode = (e) => {
        e.stopPropagation(); e.preventDefault();
        toggleNodeSelection(node.id);
    };
    const handleAddClick = (e) => {
        e.stopPropagation(); e.preventDefault();
        onAddNode(node.id);
    };

    const getLinkClassName = ({isActive}) => `node-link-content ${isActive ? "is-active" : ""}`;
    
    // Klasse für Highlights ergänzen
    const wrapperClasses = `tree-node-wrapper ${isSelected ? "is-selected" : ""} ${isHighlighted ? "is-highlighted" : ""}`;
    const lineClasses =["tree-node-line", isOver && canDrop && "is-drop-target", isOver && !canDrop && "is-drop-invalid"].filter(Boolean).join(" ");
    const selectionAreaClasses = `selection-area ${!node.icon ? "no-icon-mode" : ""}`;
    
    return (
        <div ref={wrapperRef} className={wrapperClasses} style={{ opacity: isDragging ? 0.4 : 1 }}>
            <div ref={dropRef} className={lineClasses}>
                <span className="collapse-icon" onClick={handleToggleExpand}>
                    {hasChildren && <i className={`bx ${isExpanded ? "bx-chevron-down" : "bx-chevron-right"}`}></i>}
                </span>
                <span className={selectionAreaClasses} onClick={handleSelectNode}>
                    <i className="selector-icon bx bx-checkbox"></i>
                    <i className="selector-icon-checked bx bxs-checkbox-checked"></i>
                    {node.icon && <i className={`bx ${node.icon} node-icon`}></i>}
                </span>
                <NavLink
                    to={`/vaults/${vaultId}/nodes/${node.id}`}
                    className={getLinkClassName}
                    onClick={onNodeClick}
                >
                    <span className="node-title" title={node.title}>{node.title}</span>
                </NavLink>
                <span className="add-node-icon" onClick={handleAddClick} title="Kind-Element hinzufügen">
                    <i className="bx bx-plus"></i>
                </span>
            </div>
            {hasChildren && isExpanded && (
                <div className="children-container">
                    {node.children.map((childNode) => (
                        <TreeNode
                            key={childNode.id}
                            node={childNode}
                            onAddNode={onAddNode}
                            onMoveNode={onMoveNode}
                            onNodeClick={onNodeClick}
                            highlightedNodeIds={highlightedNodeIds}
                        />
                    ))}
                </div>
            )}
        </div>
    );
});

// ============================================================================
// 3. HAUPTKOMPONENTE: ProjectTree
// ============================================================================
export default function ProjectTree({ onNodeClick, highlightedNodeIds = new Set() }) {
    const { vaultId } = useParams();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    
    // Für Auto-Expand bei der Suche benötigt
    const toggleNodeCollapse = useWorkspaceStore(state => state.toggleNodeCollapse);
    const collapsedNodes = useWorkspaceStore(state => state.collapsedNodes);

    const {
        data: treeData,
        isLoading,
        isSuccess
    } = useVaultTreeQuery(vaultId);

    // Auto-Expand von Elternknoten, damit Highlight-Treffer sichtbar werden
    useEffect(() => {
        if (!highlightedNodeIds || highlightedNodeIds.size === 0 || !treeData) return;

        const parentsToExpand = new Set();

        const findPaths = (nodes, currentPath) => {
            for (const node of nodes) {
                const path =[...currentPath, node.id];
                if (highlightedNodeIds.has(node.id)) {
                    // Füge alle Ancestor-IDs der Liste der zu expandierenden Knoten hinzu
                    currentPath.forEach(parentId => parentsToExpand.add(parentId));
                }
                if (node.children && node.children.length > 0) {
                    findPaths(node.children, path);
                }
            }
        };

        findPaths(treeData,[]);

        parentsToExpand.forEach(parentId => {
            if (collapsedNodes.has(parentId)) {
                toggleNodeCollapse(parentId);
            }
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [highlightedNodeIds, treeData]);

    const addNodeMutation = useMutation({
        mutationFn: (payload) => apiClient.post(`/api/vaults/${vaultId}/nodes/`, payload),
        onSuccess: (response) => {
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            navigate(`/vaults/${vaultId}/nodes/${response.data.id}`);
        },
        onError: (err) => {
            console.error("Fehler beim Erstellen des Elements:", err);
            alert(`Fehler: ${err.response?.data?.error || err.message}`);
        }
    });

    const moveNodeMutation = useMutation({
    mutationFn: ({ nodeIdToMove, newParentId }) =>
        apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeIdToMove}/move`, { parent_id: newParentId }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey:['vaultTree', vaultId] });
        },
        onError: (err) => {
            console.error("Fehler beim Verschieben des Elements:", err);
            alert(`Fehler: ${err.response?.data?.error || err.message}`);
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
        }
    });

    const handleAddNode = useCallback((parentId) => {
        if (!isSuccess) return;
        const title = prompt("Titel für das neue Element eingeben:");
        if (!title || !title.trim()) return;
        addNodeMutation.mutate({ title, parent_id: parentId });
    }, [isSuccess, addNodeMutation]);

    const handleMoveNode = useCallback((sourceNode, targetNode) => {
        if (!isSuccess) return;
        moveNodeMutation.mutate({
            nodeIdToMove: sourceNode.id,
            newParentId: targetNode.id
        });
    }, [isSuccess, moveNodeMutation]);

    if (isLoading) return <div className="p-2 text-muted small">Lade Baum...</div>;
    if (!treeData || treeData.length === 0) {
        return <div className="p-2 text-muted small">Dieser Vault ist noch leer.</div>;
    }

    const containerClasses =[
        "project-tree-container",
        !isSuccess ? "is-stale" : ""
    ].filter(Boolean).join(" ");

    return (
        <div className={containerClasses}>
            {treeData.map((rootNode) => (
                <TreeNode
                    key={rootNode.id}
                    node={rootNode}
                    onAddNode={handleAddNode}
                    onMoveNode={handleMoveNode}
                    onNodeClick={onNodeClick}
                    highlightedNodeIds={highlightedNodeIds}
                />
            ))}
        </div>
    );
}