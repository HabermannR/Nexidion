// src/services/clipboardService.js

/**
 * Holt den kombinierten Inhalt der ausgewählten Nodes und kopiert ihn ins Clipboard.
 * @param {Function} getContextContent - Die Funktion aus dem AppContext.
 * @returns {Promise<boolean>} - True bei Erfolg, false bei Fehler.
 */
export const copyContextContent = async (getContextContent) => {
  try {
    const { content } = await getContextContent();
    if (content) {
      await navigator.clipboard.writeText(content);
      return true;
    }
    return false; // Nichts zu kopieren
  } catch (error) {
    console.error("Failed to copy content:", error);
    return false;
  }
};

/**
 * Formatiert die Baumstruktur wie der 'tree'-Befehl und kopiert sie ins Clipboard.
 * Geht von einem einzigen Wurzelknoten in treeData aus.
 * @param {Array} treeData - Die Baumdatenstruktur mit einem einzigen Wurzelknoten.
 * @returns {Promise<boolean>} - True bei Erfolg, false bei Fehler.
 */
export const copyTreeStructure = async (treeData) => {
  // Stellt sicher, dass treeData ein Array mit mindestens einem Element ist.
  if (!treeData || treeData.length === 0) {
    return false;
  }

  // Rekursive Hilfsfunktion zur Erstellung der Baumstruktur
  const formatNodeRecursive = (node, prefix, isLast) => {
    // Bestimmt den Connector basierend darauf, ob es das letzte Element ist
    const connector = isLast ? '└── ' : '├── ';
    let output = prefix + connector + node.title + '\n';

    // Berechnet das Präfix für die Kind-Elemente
    const childPrefix = prefix + (isLast ? '    ' : '│   ');

    if (node.children && node.children.length > 0) {
      node.children.forEach((child, index) => {
        const isLastChild = index === node.children.length - 1;
        output += formatNodeRecursive(child, childPrefix, isLastChild);
      });
    }
    return output;
  };
  
  // Da es nur einen Wurzelknoten gibt, greifen wir direkt darauf zu.
  const rootNode = treeData[0];
  
  // Beginne den Output mit dem Titel des Wurzelknotens.
  let formattedTree = rootNode.title + '\n';

  // Verarbeite die direkten Kinder des Wurzelknotens.
  if (rootNode.children && rootNode.children.length > 0) {
    rootNode.children.forEach((child, index) => {
      const isLastChild = index === rootNode.children.length - 1;
      // Der initiale Präfix für die Kinder der ersten Ebene ist leer.
      // Die Hilfsfunktion fügt dann den ersten Connector hinzu.
      formattedTree += formatNodeRecursive(child, '', isLastChild);
    });
  }

  try {
    // .trim() entfernt den letzten überflüssigen Zeilenumbruch.
    await navigator.clipboard.writeText(formattedTree.trim());
    return true;
  } catch (error) {
    console.error("Failed to copy tree:", error);
    return false;
  }
};