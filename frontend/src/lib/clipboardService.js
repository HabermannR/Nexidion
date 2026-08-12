// src/services/clipboardService.js

/**
 * Gets the combined content of the selected nodes and copies it to the clipboard.
 * @param {Function} getContextContent - The function from the AppContext.
 * @returns {Promise<boolean>} - True on success, false on error.
 */
export const copyContextContent = async (getContextContent) => {
  if (!navigator.clipboard) {
    // Throw an error with a clear message
    throw new Error("Copying to the clipboard is only possible in a secure context (HTTPS).");
  }
  try {
    const { content } = await getContextContent();
    if (content) {
      await navigator.clipboard.writeText(content);
      // No "return true" necessary anymore, success is signaled by the absence of an error.
    }
  } catch (error) {
    console.error("Failed to copy content:", error);
    // Rethrow the original error or a new, more user-friendly one.
    throw new Error("Content could not be copied to the clipboard.");
  }
};

/**
 * Formats the tree structure and copies it to the clipboard.
 * @param {Array} treeData - The tree data structure.
 * @throws {Error} - Throws an error if the API is not available or copying fails.
 */
export const copyTreeStructure = async (treeData) => {
  // CHECK 1: API availability
  if (!navigator.clipboard) {
    throw new Error("Copying is only possible in a secure context (HTTPS or localhost).");
  }

  // CHECK 2: Valid data
  if (!treeData || treeData.length === 0 || !treeData[0]) {
    // This is rather an internal error, but we catch it.
    throw new Error("No data available to copy.");
  }

  // Recursive helper function to create the tree structure
  const formatNodeRecursive = (node, prefix, isLast) => {
    // Determines the connector based on whether it is the last element
    const connector = isLast ? '└── ' : '├── ';

    // +++ CHANGED: Add the node ID (UUID) +++
    let output = prefix + connector + `${node.title} (${node.id})` + '\n';

    // Calculates the prefix for the child elements
    const childPrefix = prefix + (isLast ? '    ' : '│   ');

    if (node.children && node.children.length > 0) {
      node.children.forEach((child, index) => {
        const isLastChild = index === node.children.length - 1;
        output += formatNodeRecursive(child, childPrefix, isLastChild);
      });
    }
    return output;
  };

  // Loop over ALL root nodes so nothing is silently dropped.
  let formattedTree = '';
  treeData.forEach((rootNode, rootIndex) => {
    // Separate multiple roots with a blank line
    if (rootIndex > 0) formattedTree += '\n';
    formattedTree += `${rootNode.title} (${rootNode.id})` + '\n';
    if (rootNode.children && rootNode.children.length > 0) {
      rootNode.children.forEach((child, index) => {
        const isLastChild = index === rootNode.children.length - 1;
        formattedTree += formatNodeRecursive(child, '', isLastChild);
      });
    }
  });

  try {
    await navigator.clipboard.writeText(formattedTree.trim());
  } catch (error) {
    console.error("Failed to copy tree:", error);
    // Throw a new, user-friendly error.
    throw new Error("The tree structure could not be copied to the clipboard.");
  }
};