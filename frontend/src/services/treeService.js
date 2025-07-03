// src/services/treeService.js

/**
 * Durchläuft den Baum und gibt die IDs der zu findenden Knoten in ihrer
 * visuellen Reihenfolge (Depth-First) zurück.
 * @param {Array} nodes - Die komplette Baumdatenstruktur (z.B. treeData).
 * @param {Set<number|string>} idsToFind - Ein Set mit den IDs der gesuchten Knoten.
 * @returns {Array<number|string>} - Ein Array der gefundenen IDs in der richtigen Reihenfolge.
 */
export const getIdsInOrder = (nodes, idsToFind) => {
    let orderedIds = [];
    if (!nodes || !idsToFind || idsToFind.size === 0) {
        return orderedIds;
    }

    function traverse(node) {
        if (idsToFind.has(node.id)) {
            orderedIds.push(node.id);
        }
        if (node.children) {
            for (const child of node.children) {
                traverse(child);
            }
        }
    }

    for (const rootNode of nodes) {
        traverse(rootNode);
    }
    return orderedIds;
};

/**
 * Durchläuft den Baum und gibt die ausgewählten Nodes als strukturiertes
 * Array für ein Inhaltsverzeichnis (Table of Contents) zurück.
 * @param {Array} nodes - Die komplette Baumdatenstruktur.
 * @param {Set<number|string>} selectedIds - Ein Set der ausgewählten Node-IDs.
 * @returns {Array<{id: number|string, title: string, level: number}>} - Das Inhaltsverzeichnis.
 */
export const generateTocForSelectedNodes = (nodes, selectedIds) => {
    const toc = [];
    if (!nodes || !selectedIds || selectedIds.size === 0) {
        return toc;
    }

    const traverse = (node, level) => {
        let isSelected = selectedIds.has(node.id);
        if (isSelected) {
            toc.push({ id: node.id, title: node.title, level: level });
        }

        if (node.children) {
            // Wichtig: Das Level für die Kinder nur erhöhen, wenn der Parent auch im ToC ist.
            const newLevel = isSelected ? level + 1 : level;
            for (const child of node.children) {
                traverse(child, newLevel);
            }
        }
    };

    for (const rootNode of nodes) {
        traverse(rootNode, 0);
    }

    // Normalisiere die Level, damit sie immer bei 0 beginnen
    if (toc.length > 0) {
        const minLevel = Math.min(...toc.map(item => item.level));
        toc.forEach(item => item.level -= minLevel);
    }
    
    return toc;
};