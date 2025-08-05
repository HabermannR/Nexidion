// WESENTLICHE ÄNDERUNGEN:
// - useLoaderData, useRevalidator wurden entfernt.
// - useNavigate wird nur noch für die tatsächliche Navigation verwendet, nicht zum Neuladen.
// - NEU: useQuery zum Laden des Baums.
// - NEU: useMutation für das Hinzufügen und Verschieben von Nodes.
// - NEU: useQueryClient, um die Daten nach einer Mutation gezielt zu invalidieren.

import React, { useCallback, useRef } from "react";
import { NavLink, useParams, useNavigate } from "react-router-dom";
import { useDrag, useDrop } from "react-dnd";
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'; // NEU
import apiClient from "../../../api/apiClient.js";
import { useWorkspaceStore } from '../workspaceStore.js';
import "./ProjectTree.css";

const ItemTypes = { NODE: "NODE" };

// ============================================================================
// TreeNode Komponente (bleibt unverändert, da sie die Handler als Props erhält)
// ============================================================================
const TreeNode = React.memo(({ node, onAddNode, onMoveNode }) => {
    // ... (keine Änderungen an dieser inneren Komponente erforderlich)
    const wrapperRef = useRef(null);
    const dropRef = useRef(null);

    const { collapsedNodes, toggleNodeCollapse, selectedNodeIds, toggleNodeSelection } = useWorkspaceStore();
    const isSelected = selectedNodeIds.has(node.id);
    const isExpanded = !collapsedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;

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
    const wrapperClasses = `tree-node-wrapper ${isSelected ? "is-selected" : ""}`;
    const lineClasses = ["tree-node-line", isOver && canDrop && "is-drop-target", isOver && !canDrop && "is-drop-invalid"].filter(Boolean).join(" ");

    return (
        <div ref={wrapperRef} className={wrapperClasses} style={{ opacity: isDragging ? 0.4 : 1 }}>
            <div ref={dropRef} className={lineClasses}>
                <span className="collapse-icon" onClick={handleToggleExpand}>
                    {hasChildren && <i className={`bx ${isExpanded ? "bx-chevron-down" : "bx-chevron-right"}`}></i>}
                </span>
                <span className="selection-area" onClick={handleSelectNode}>
                    <i className="selector-icon bx bx-checkbox"></i>
                    <i className="selector-icon-checked bx bxs-checkbox-checked"></i>
                    <i className={`bx ${node.icon} node-icon`}></i>
                </span>
                <NavLink to={`/vaults/${node.vault_id}/nodes/${node.id}`} className={getLinkClassName}>
                    <span className="node-title" title={node.title}>{node.title}</span>
                </NavLink>
                <span className="add-node-icon" onClick={handleAddClick} title="Kind-Element hinzufügen">
                    <i className="bx bx-plus"></i>
                </span>
            </div>
            {hasChildren && isExpanded && (
                <div className="children-container">
                    {node.children.map((childNode) => (
                        <TreeNode key={childNode.id} node={childNode} onAddNode={onAddNode} onMoveNode={onMoveNode}/>
                    ))}
                </div>
            )}
        </div>
    );
});


// ============================================================================
// 3. HAUPTKOMPONENTE: ProjectTree (V4-Architektur mit useQuery & useMutation)
// ============================================================================
export default function ProjectTree() {
    const { vaultId } = useParams();
    const navigate = useNavigate();
    const queryClient = useQueryClient(); // NEU: QueryClient für Invalidierung

    // NEU: Daten mit useQuery laden. Ersetzt useLoaderData.
    const { data: treeData, isLoading } = useQuery({
        queryKey: ['vaultTree', vaultId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes?format=tree&v3=true`).then(res => res.data),
        enabled: !!vaultId,
    });

    // NEU: Mutation für das Hinzufügen eines Nodes.
    const addNodeMutation = useMutation({
        mutationFn: (payload) => apiClient.post(`/api/vaults/${vaultId}/nodes/`, payload),
        onSuccess: (response) => {
            console.log("Element erfolgreich erstellt!");
            // 1. Baum-Daten invalidieren, um die UI zu aktualisieren
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            // 2. Zum neuen Element navigieren (ohne Reload-Tricks)
            navigate(`/vaults/${vaultId}/nodes/${response.data.id}`);
        },
        onError: (err) => {
            console.error("Fehler beim Erstellen des Elements:", err);
            alert(`Fehler: ${err.response?.data?.error || err.message}`);
        }
    });

    // NEU: Mutation für das Verschieben eines Nodes.
    const moveNodeMutation = useMutation({
        mutationFn: ({ nodeIdToMove, newParentId }) =>
            apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeIdToMove}`, { parent_id: newParentId }),
        onSuccess: () => {
            console.log("Element erfolgreich verschoben!");
            // Baum-Daten invalidieren, um die UI zu aktualisieren. Keine Navigation nötig.
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
        },
        onError: (err) => {
            console.error("Fehler beim Verschieben des Elements:", err);
            alert(`Fehler: ${err.response?.data?.error || err.message}`);
            // Bei Fehler trotzdem neu laden, um einen konsistenten Zustand sicherzustellen
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
        }
    });

    const handleAddNode = useCallback((parentId) => {
        if (!vaultId) return;
        const title = prompt("Titel für das neue Element eingeben:");
        if (!title || !title.trim()) return;
        addNodeMutation.mutate({ title, parent_id: parentId });
    }, [vaultId, addNodeMutation]);

    const handleMoveNode = useCallback((sourceNode, targetNode) => {
        if (!vaultId) return;
        moveNodeMutation.mutate({
            nodeIdToMove: sourceNode.id,
            newParentId: targetNode.id
        });
    }, [vaultId, moveNodeMutation]);


    if (isLoading) return <div className="p-2 text-muted small">Lade Baum...</div>;
    if (!treeData || treeData.length === 0) {
        return <div className="p-2 text-muted small">Dieser Vault ist noch leer.</div>;
    }

    return (
        <div className="project-tree-container">
            {treeData.map((rootNode) => (
                <TreeNode
                    key={rootNode.id}
                    node={rootNode}
                    onAddNode={handleAddNode}
                    onMoveNode={handleMoveNode}
                />
            ))}
        </div>
    );
}