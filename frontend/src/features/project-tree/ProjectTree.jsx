// src/features/project-tree/ProjectTree.jsx

import React, { useCallback, useRef, useEffect } from "react";
import { NavLink, useParams, useNavigate } from "react-router-dom";
import { useDrag, useDrop } from "react-dnd";
import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from "../../api/apiClient.js";
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery.js';
import { useToast } from '../../components/ToastProvider.jsx';
import "./ProjectTree.css";

const ItemTypes = { NODE: "NODE" };

// ============================================================================
// TreeNode Komponente
// ============================================================================
const TreeNode = React.memo(({ node, onAddNode, onMoveNode, onNodeClick, highlightedNodeIds = new Set(), scrollToNodeId }) => {
    const { vaultId } = useParams();
    const wrapperRef = useRef(null);
    const dropRef = useRef(null);

    const { collapsedNodes, toggleNodeCollapse, selectedNodeIds, toggleNodeSelection } = useWorkspaceStore();
    const isSelected = selectedNodeIds.has(node.id);
    const isExpanded = !collapsedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;

    const isHighlighted = highlightedNodeIds.has(node.id);
    const isSearchFocused = scrollToNodeId === node.id;

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

    const wrapperClasses = `tree-node-wrapper ${isSelected ? "is-selected" : ""} ${isHighlighted ? "is-highlighted" : ""} ${isSearchFocused ? "is-search-focused" : ""}`;
    const lineClasses = ["tree-node-line", isOver && canDrop && "is-drop-target", isOver && !canDrop && "is-drop-invalid"].filter(Boolean).join(" ");
    const selectionAreaClasses = `selection-area ${!node.icon ? "no-icon-mode" : ""}`;

    return (
        <div ref={wrapperRef} className={wrapperClasses} style={{ opacity: isDragging ? 0.4 : 1 }} data-node-id={node.id}>
            <div ref={dropRef} className={lineClasses}>
                <span className="collapse-icon" onClick={handleToggleExpand}>
                    {hasChildren && <i className={`bx ${isExpanded ? "bx-chevron-down" : "bx-chevron-right"}`}></i>}
                </span>

                <span className={selectionAreaClasses} onClick={handleSelectNode}>
                    <i className="selector-icon bx bx-checkbox"></i>
                    <i className="selector-icon-checked bx bxs-checkbox-checked"></i>
                    {node.icon && <i className={`bx ${node.icon} node-icon`}></i>}
                </span>

                {/* 1. MOVED PLUS ICON TO THE FRONT */}
                <span className="add-node-icon" onClick={handleAddClick} title="Kind-Element hinzufügen">
                    <i className="bx bx-plus"></i>
                </span>

                <NavLink
                    to={`/vaults/${vaultId}/nodes/${node.id}`}
                    className={getLinkClassName}
                    onClick={onNodeClick}
                >
                    <span className="node-title" title={node.title}>{node.title}</span>
                </NavLink>
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
                            scrollToNodeId={scrollToNodeId}
                        />
                    ))}
                </div>
            )}
        </div>
    );
});

// ============================================================================
// HAUPTKOMPONENTE: ProjectTree
// ============================================================================
export default function ProjectTree({ onNodeClick, highlightedNodeIds = new Set(), scrollToNodeId = null }) {
    const { vaultId } = useParams();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const toast = useToast();

    const toggleNodeCollapse = useWorkspaceStore(state => state.toggleNodeCollapse);
    const collapsedNodes = useWorkspaceStore(state => state.collapsedNodes);

    const { data: vaultTreeData, isLoading, isSuccess } = useVaultTreeQuery(vaultId);
    const treeData = vaultTreeData?.tree || null;

    useEffect(() => {
        if (!highlightedNodeIds || highlightedNodeIds.size === 0 || !treeData) return;

        const parentsToExpand = new Set();
        const findPaths = (nodes, currentPath) => {
            for (const node of nodes) {
                const path = [...currentPath, node.id];
                if (highlightedNodeIds.has(node.id)) {
                    currentPath.forEach(parentId => parentsToExpand.add(parentId));
                }
                if (node.children && node.children.length > 0) {
                    findPaths(node.children, path);
                }
            }
        };

        findPaths(treeData, []);

        parentsToExpand.forEach(parentId => {
            if (collapsedNodes.has(parentId)) {
                toggleNodeCollapse(parentId);
            }
        });
    }, [highlightedNodeIds, treeData]);

    useEffect(() => {
        if (!scrollToNodeId) return;
        const timer = setTimeout(() => {
            const elements = document.querySelectorAll(`[data-node-id="${scrollToNodeId}"]`);
            elements.forEach(el => {
                const isVisible = el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0;
                if (isVisible) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        }, 80);

        return () => clearTimeout(timer);
    }, [scrollToNodeId]);

    const addNodeMutation = useMutation({
        mutationFn: (payload) => apiClient.post(`/api/vaults/${vaultId}/nodes/`, payload),
        onSuccess: (response) => {
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            navigate(`/vaults/${vaultId}/nodes/${response.data.id}`);
        },
        onError: (err) => {
            const msg = err.response?.data?.error || err.message;
            if (err.response?.status === 403) {
                toast.error('Node limit reached — you\'ve hit the maximum number of nodes for this vault.');
            } else {
                toast.error(`Failed to create node: ${msg}`);
            }
        }
    });

    const moveNodeMutation = useMutation({
        mutationFn: ({ nodeIdToMove, newParentId }) =>
            apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeIdToMove}/move`, { parent_id: newParentId }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
        },
        onError: (err) => {
            toast.error(`Failed to move node: ${err.response?.data?.error || err.message}`);
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
        }
    });

    const handleAddNode = useCallback((parentId) => {
        if (!isSuccess) return;
        const title = prompt("Title for new node:");
        if (!title || !title.trim()) return;
        addNodeMutation.mutate({ title: title.trim(), parent_id: parentId });
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

    const containerClasses = ["project-tree-container", !isSuccess ? "is-stale" : ""].filter(Boolean).join(" ");

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
                    scrollToNodeId={scrollToNodeId}
                />
            ))}
        </div>
    );
}