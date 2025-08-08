// src/services/clipboardService.js

/**
 * Holt den kombinierten Inhalt der ausgewählten Nodes und kopiert ihn ins Clipboard.
 * @param {Function} getContextContent - Die Funktion aus dem AppContext.
 * @returns {Promise<boolean>} - True bei Erfolg, false bei Fehler.
 */
export const copyContextContent = async (getContextContent) => {
  if (!navigator.clipboard) {
    // Wirf einen Fehler mit einer klaren Nachricht
    throw new Error("Kopieren in die Zwischenablage ist nur in einem sicheren Kontext (HTTPS) möglich.");
  }
  try {
    const { content } = await getContextContent();
    if (content) {
      await navigator.clipboard.writeText(content);
      // Kein "return true" mehr nötig, Erfolg wird durch das Ausbleiben eines Fehlers signalisiert.
    }
  } catch (error) {
    console.error("Failed to copy content:", error);
    // Wirf den ursprünglichen Fehler weiter oder einen neuen, benutzerfreundlicheren.
    throw new Error("Inhalt konnte nicht in die Zwischenablage kopiert werden.");
  }
};

/**
 * Formatiert die Baumstruktur und kopiert sie ins Clipboard.
 * @param {Array} treeData - Die Baumdatenstruktur.
 * @throws {Error} - Wirft einen Fehler, wenn die API nicht verfügbar ist oder das Kopieren fehlschlägt.
 */
export const copyTreeStructure = async (treeData) => {
  // PRÜFUNG 1: API-Verfügbarkeit
  if (!navigator.clipboard) {
    throw new Error("Kopieren ist nur in einem sicheren Kontext (HTTPS oder localhost) möglich.");
  }

  // PRÜFUNG 2: Gültige Daten
  if (!treeData || treeData.length === 0 || !treeData[0]) {
    // Dies ist eher ein interner Fehler, aber wir fangen ihn ab.
    throw new Error("Keine Daten zum Kopieren vorhanden.");
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
      formattedTree += formatNodeRecursive(child, '', isLastChild);
    });
  }

  try {
    await navigator.clipboard.writeText(formattedTree.trim());
  } catch (error) {
    console.error("Failed to copy tree:", error);
    // Wirf einen neuen, für den Benutzer verständlichen Fehler.
    throw new Error("Die Baumstruktur konnte nicht in die Zwischenablage kopiert werden.");
  }
};