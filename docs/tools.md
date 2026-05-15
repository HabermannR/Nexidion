# Navigation, Tools & Export

Nexidion provides several built-in features to navigate your workspace and securely extract, export, or copy your knowledge out of your vault. Export tools can be accessed via the **Tools** tab on the right-hand panel.

## 1. Search & Tree Navigation

**Searching Nodes:**
Directly above the navigation tree on the left, you will find the search bar. Nexidion uses **full-text search (FTS)** powered by PostgreSQL, with support for both **English and German** stemming and stop-word filtering out of the box. Results are ranked by relevance using PostgreSQL's built-in text ranking — matches are weighted by term frequency and position — and the 20 highest-scoring results are returned. You can quickly cycle through these top results using the arrow buttons next to the search bar.

**Navigating the Tree:**
You can manually expand or collapse individual parent nodes by clicking the arrows next to them in the tree. For a quicker overview, use the two global expand/collapse buttons located just above the search bar to instantly open or close your entire vault structure.

---

## 2. Selecting Nodes for Actions

Most tools require you to select which nodes you want to operate on.

To select a node, look at the navigation tree. Hover your mouse over a node — its icon will turn into a checkbox — then click it.

---

## 3. Copying Content to Clipboard

The Copy tools allow you to quickly extract Markdown content from your vault to paste into emails, text editors, or external chat systems.

Once you have selected one or more nodes, you can copy them from the **Tools** tab on the right.
*(For convenience, a quick-copy button is also located at the very bottom of the left-hand navigation tree, right next to a **Clear** button which instantly deselects all currently selected nodes).*

**Tree Export Options:**
From the Tools tab, you can export the full Markdown tree of your selected nodes. You can customize this export using the following toggles:
*   **Include UUIDs:** When enabled, the hidden internal ID of the node is included at the top of the copied text. This is highly useful if you are pasting the text into an external system (or providing context to an external AI) and want to maintain a strict reference back to the original Nexidion node.
*   **Include AI Summaries:** If your nodes have AI-generated summary blocks attached to them, you can choose to include or exclude them from the copied text.

*Security Note: To prevent data leakage, Nexidion's backend will automatically block any attempt to copy or export nodes that do not belong to your currently active vault.*

---

## 4. Exporting & Printing

Nexidion includes a custom backend rendering engine to generate clean, readable exports of your nodes.

*   **Print Selected Nodes:** Select specific nodes and click this button in the Tools tab to generate a clean, distraction-free HTML page of your content. From this view, you can easily use your browser's native print function (`Ctrl+P` or `Cmd+P`) to "Save as PDF" or send it to a physical printer.
*   **Print Entire Vault:** If you want a complete physical backup or to read your entire knowledge base offline, click "Print Entire Vault". This will sequentially render every single node in your currently active vault into one large, readable document. For vaults with hundreds of nodes or large amounts of content, this may take a moment to generate.
