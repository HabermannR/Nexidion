import React, { useState } from 'react';
import { useLoaderData, NavLink } from 'react-router-dom';
import './ProjectTree.css'; // Das CSS bleibt in seiner eigenen Datei

// ============================================================================
// 1. UNTERKOMPONENTE: TreeNode
// Stellt einen einzelnen, rekursiven Knoten im Baum dar.
// `React.memo` ist eine Performance-Optimierung.
// ============================================================================
const TreeNode = React.memo(({ node }) => {
    // Lokaler State nur für diese eine Knoten-Instanz. Perfekt für UI-Zustand.
    const [isExpanded, setIsExpanded] = useState(true);

    const hasChildren = node.children && node.children.length > 0;

    // Handler, um den auf-/zugeklappten Zustand zu toggeln.
    const handleToggleExpand = (e) => {
        // Verhindert, dass der Klick auf den Pfeil auch den NavLink auslöst.
        e.stopPropagation();
        e.preventDefault();
        if (hasChildren) {
            setIsExpanded(!isExpanded);
        }
    };

    // Die NavLink Komponente ist der Schlüssel. Sie weiß selbst, ob sie "aktiv" ist.
    // Wir übergeben eine Funktion an `className`, um den Stil dynamisch zu setzen.
    const getLinkClassName = ({ isActive }) => {
        return `node-link-content ${isActive ? 'active' : ''}`;
    };

    return (
        <div className="tree-node-wrapper">
            <NavLink to={`/vaults/${node.vault_id}/nodes/${node.id}`} className={getLinkClassName}>
                {/* Expand/Collapse Pfeil */}
                <span className="collapse-icon" onClick={handleToggleExpand}>
                    {hasChildren && (
                        <i className={`bx ${isExpanded ? 'bx-chevron-down' : 'bx-chevron-right'}`}></i>
                    )}
                </span>

                {/* Das eigentliche Node-Icon aus den Backend-Daten */}
                <i className={`node-icon ${node.icon}`}></i>

                {/* Der Titel des Nodes */}
                <span className="node-title" title={node.title}>
                    {node.title}
                </span>
            </NavLink>

            {/* Rekursiver Teil: Rendere die Kinder, wenn der Knoten ausgeklappt ist */}
            {hasChildren && isExpanded && (
                <div className="children-container">
                    {node.children.map(childNode => (
                        <TreeNode key={childNode.id} node={childNode} />
                    ))}
                </div>
            )}
        </div>
    );
});


// ============================================================================
// 2. HAUPTKOMPONENTE (Export): ProjectTree
// Der Container für die gesamte Baumansicht.
// Holt die Baumdaten und startet die Rekursion.
// ============================================================================
export default function ProjectTree() {
    // Holt die Daten, die vom `vaultTreeLoader` bereitgestellt wurden.
    const treeData = useLoaderData();
    console.log("Daten, die in ProjectTree ankommen:", treeData);

    // Lade- oder Fehlerzustand
    if (!treeData) {
        return <div className="p-2 text-muted small">Lade Baum...</div>;
    }

    // Fall: Der Vault ist leer
    if (treeData.length === 0) {
        return <div className="p-2 text-muted small">Dieser Vault ist noch leer.</div>;
    }

    return (
        <div className="project-tree-container">
            {treeData.map(rootNode => (
                <TreeNode key={rootNode.id} node={rootNode} />
            ))}
        </div>
    );
}