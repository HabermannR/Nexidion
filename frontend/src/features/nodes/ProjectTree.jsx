import React, {useCallback, useRef} from "react"; // useEffect ist hier nicht mehr nötig
import {
    useLoaderData,
    NavLink,
    useParams,
    useRevalidator,
    useNavigate,
} from "react-router-dom";
import {useDrag, useDrop} from "react-dnd"; // useDragLayer wurde entfernt
// getEmptyImage wird nicht mehr benötigt
import apiClient from "../../api/apiClient";
import {useContextStore} from "../context/contextStore.js";
import "./ProjectTree.css";

const ItemTypes = {NODE: "NODE"};

// ============================================================================
// 1. CustomDragLayer Komponente wurde komplett entfernt.
// Wir nutzen jetzt die eingebaute Vorschau des Browsers.
// ============================================================================

// ============================================================================
// 2. TreeNode Komponente (angepasst für Standard-Drag-Preview)
// ============================================================================
const TreeNode = React.memo(({node, onAddNode, onMoveNode}) => {
    // WICHTIG: Zwei Refs - eine für den ganzen ziehbaren Wrapper, eine nur für das Drop-Ziel
    const wrapperRef = useRef(null);
    const dropRef = useRef(null);

    const {
        collapsedNodes,
        toggleNodeCollapse,
        selectedNodeIds,
        toggleNodeSelection,
    } = useContextStore();
    const isSelected = selectedNodeIds.has(node.id);
    const isExpanded = !collapsedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;

    // --- DRAG-AND-DROP LOGIK ---

    // dragPreview wird hier nicht mehr benötigt.
    const [{isDragging}, drag] = useDrag(() => ({
        type: ItemTypes.NODE,
        // Das Item braucht nur noch die Daten, die für die Drop-Logik wichtig sind.
        item: {id: node.id, parent_id: node.parent_id},
        collect: (monitor) => ({isDragging: !!monitor.isDragging()}),
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

    // =======================================================================
    // HIER IST DIE NEUE ZUWEISUNG:
    // 1. Der GANZE WRAPPER (inkl. Kinder) wird ziehbar gemacht (`drag`).
    drag(wrapperRef);
    // 2. NUR DIE EINE ZEILE wird zum Ablageziel (`drop`).
    drop(dropRef);
    // =======================================================================

    // Der useEffect, der dragPreview(getEmptyImage()) aufgerufen hat, wurde entfernt.
    // Dadurch wird die Standard-Vorschau des Browsers automatisch aktiviert.

    // --- EVENT HANDLERS & KLASSEN ---
    const handleToggleExpand = (e) => {
        e.stopPropagation();
        e.preventDefault();
        if (hasChildren) {
            toggleNodeCollapse(node.id);
        }
    };
    const handleSelectNode = (e) => {
        e.stopPropagation();
        e.preventDefault();
        toggleNodeSelection(node.id);
    };
    const handleAddClick = (e) => {
        e.stopPropagation();
        e.preventDefault();
        onAddNode(node.id);
    };

    const getLinkClassName = ({isActive}) =>
        `node-link-content ${isActive ? "is-active" : ""}`;
    const wrapperClasses = `tree-node-wrapper ${isSelected ? "is-selected" : ""}`;
    const lineClasses = [
        "tree-node-line",
        isOver && canDrop && "is-drop-target",
        isOver && !canDrop && "is-drop-invalid",
    ]
        .filter(Boolean)
        .join(" ");

    return (
        // Die ref für das Ziehen wird hier auf den äußeren Container angewendet.
        // Der Browser macht nun einen "Screenshot" von diesem ganzen Block.
        <div
            ref={wrapperRef}
            className={wrapperClasses}
            style={{opacity: isDragging ? 0.4 : 1}}
        >
            {/* Die ref für das Ablegen wird nur hier auf der Zeile angewendet. */}
            <div ref={dropRef} className={lineClasses}>
        <span className="collapse-icon" onClick={handleToggleExpand}>
          {hasChildren && (
              <i
                  className={`bx ${isExpanded ? "bx-chevron-down" : "bx-chevron-right"}`}
              ></i>
          )}
        </span>
                <span className="selection-area" onClick={handleSelectNode}>
          <i className="selector-icon bx bx-checkbox"></i>
          <i className="selector-icon-checked bx bxs-checkbox-checked"></i>
          <i className={`bx ${node.icon} node-icon`}></i>
        </span>
                <NavLink
                    to={`/vaults/${node.vault_id}/nodes/${node.id}`}
                    className={getLinkClassName}
                >
          <span className="node-title" title={node.title}>
            {node.title}
          </span>
                </NavLink>
                <span
                    className="add-node-icon"
                    onClick={handleAddClick}
                    title="Kind-Element hinzufügen"
                >
          <i className="bx bx-plus"></i>
        </span>
            </div>

            {/* Dieser Container wird nun Teil des "Screenshots" für die Drag-Vorschau */}
            {hasChildren && isExpanded && (
                <div className="children-container">
                    {node.children.map((childNode) => (
                        <TreeNode
                            key={childNode.id}
                            node={childNode}
                            onAddNode={onAddNode}
                            onMoveNode={onMoveNode}
                        />
                    ))}
                </div>
            )}
        </div>
    );
});

// ============================================================================
// 3. HAUPTKOMPONENTE: ProjectTree (ohne CustomDragLayer)
// ============================================================================
export default function ProjectTree() {
    const treeData = useLoaderData();
    const {vaultId} = useParams();
    const revalidator = useRevalidator();
    const navigate = useNavigate();

    const handleAddNode = useCallback(
        async (parentId) => {
            if (!vaultId) return;
            const title = prompt("Titel für das neue Element eingeben:");
            if (!title || !title.trim()) return;
            try {
                const payload = {title, parent_id: parentId};
                const response = await apiClient.post(
                    `/api/vaults/${vaultId}/nodes/`,
                    payload,
                );
                revalidator.revalidate();
                navigate(`/vaults/${vaultId}/nodes/${response.data.id}`);
                console.log("Element erfolgreich erstellt!");
            } catch (err) {
                console.error("Fehler beim Erstellen des Elements:", err);
                alert(`Fehler: ${err.response?.data?.error || err.message}`);
            }
        },
        [vaultId, revalidator, navigate],
    );

    const handleMoveNode = useCallback(
        async (sourceNode, targetNode) => {
            if (!vaultId) return;
            const nodeIdToMove = sourceNode.id;
            const newParentId = targetNode.id;
            try {
                await apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeIdToMove}`, {
                    parent_id: newParentId,
                });
                revalidator.revalidate();
            } catch (err) {
                console.error("Fehler beim Verschieben des Elements:", err);
                alert(`Fehler: ${err.response?.data?.error || err.message}`);
                revalidator.revalidate();
            }
        },
        [vaultId, revalidator],
    );

    if (!treeData)
        return <div className="p-2 text-muted small">Lade Baum...</div>;
    if (treeData.length === 0)
        return (
            <div className="p-2 text-muted small">Dieser Vault ist noch leer.</div>
        );

    return (
        <div className="project-tree-container">
            {/* Die CustomDragLayer wurde hier entfernt */}
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
