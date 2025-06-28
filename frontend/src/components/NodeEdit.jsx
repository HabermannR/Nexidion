import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom'; // WICHTIG: Import für das Druck-Portal
import { useParams, useNavigate } from 'react-router-dom';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import TreeView from 'react-treeview';
import Modal from 'react-modal';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { marked } from 'marked'; // Import von marked

import api from '../api/axios';
import { useAppContext } from '../context/AppContext';
import Chat from './Chat';
import IFSLandkarte from './IFSLandkarte';

import './NodeEdit.css';
import 'react-treeview/react-treeview.css';

Modal.setAppElement('#root');

// ============================================================================
// #region HELPER & SUB-COMPONENTS
// ============================================================================

// EPUB Generator Funktion - JETZT MIT KORREKTER ToC-VERSCHACHTELUNG
const generateEpub = async (nodes, toc) => {
    const JSZip = (await import('jszip')).default;
    const zip = new JSZip();

    // SCHRITT 1: Die "Landkarte" (Lookup-Map) erstellen
    const titleToFilenameMap = new Map();
    nodes.forEach((node, index) => {
        titleToFilenameMap.set(node.title, `chapter${index + 1}.xhtml`);
    });

    // SCHRITT 2: Den Markdown-Parser (`marked`) konfigurieren
    const internalLinkExtension = {
        name: 'internalLink',
        level: 'inline',
        start(src) { return src.indexOf('[['); },
        tokenizer(src, tokens) {
            const rule = /^\[\[\s*([^|\]\s][^|\]]*?)\s*(?:\|\s*(.+?)\s*)?\]\]/;
            const match = rule.exec(src);
            if (match) {
                const targetTitle = match[1].trim();
                const displayText = (match[2] || match[1]).trim();
                return {
                    type: 'internalLink',
                    raw: match[0],
                    target: targetTitle,
                    text: displayText,
                };
            }
        },
        renderer(token) {
            const filename = titleToFilenameMap.get(token.target);
            if (filename) {
                return `<a href="${filename}">${token.text}</a>`;
            } else {
                return `<em class="internal-link-static">${token.text}</em>`;
            }
        },
    };
    
    marked.use({ extensions: [internalLinkExtension] });


    // EPUB Struktur erstellen
    zip.file("mimetype", "application/epub+zip", {compression: "STORE"});

    // META-INF/container.xml
    zip.folder("META-INF").file("container.xml", `<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>`);

    const oebpsFolder = zip.folder("OEBPS");

    // ========================================================================
    // KORRIGIERTE LOGIK FÜR DAS INHALTSVERZEICHNIS
    // ========================================================================
    const generateNavContent = () => {
        let html = '';
        let currentLevel = -1;

        for (const item of toc) {
            const chapterIndex = nodes.findIndex(n => n.id === item.id);
            if (chapterIndex === -1) continue;
            const chapterFilename = `chapter${chapterIndex + 1}.xhtml`;

            // Schließe Ebenen, wenn wir im Baum nach oben gehen
            while (item.level < currentLevel) {
                html += '</li></ol>';
                currentLevel--;
            }

            // Öffne eine neue Ebene, wenn wir tiefer gehen
            if (item.level > currentLevel) {
                html += '<ol>';
            } else { // Gleiche Ebene, schließe das vorherige <li>
                html += '</li>';
            }

            // Füge das aktuelle Element hinzu
            html += `<li><a href="${chapterFilename}">${item.title.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</a>`;
            currentLevel = item.level;
        }

        // Schließe alle am Ende noch offenen Tags
        while (currentLevel >= 0) {
            html += '</li></ol>';
            currentLevel--;
        }

        return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>Inhaltsverzeichnis</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
    <h1>Inhaltsverzeichnis</h1>
    <nav epub:type="toc" id="toc">
        ${html}
    </nav>
</body>
</html>`;
    };
    
    const navContent = generateNavContent();
    oebpsFolder.file("nav.xhtml", navContent);


    // content.opf (Manifest) - Aktualisiert für EPUB 3
    const manifestItems = nodes.map((node, index) =>
        `<item id="chapter${index + 1}" href="chapter${index + 1}.xhtml" media-type="application/xhtml+xml"/>`
    ).join('\n    ');

    const spineItems = nodes.map((node, index) =>
        `<itemref idref="chapter${index + 1}"/>`
    ).join('\n    ');

    const bookTitle = "Knowledge Base Export";
    const bookId = `kb-export-${Date.now()}`;

    oebpsFolder.file("content.opf", `<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>${bookTitle}</dc:title>
        <dc:creator>Knowledge Base</dc:creator>
        <dc:identifier id="bookid">${bookId}</dc:identifier>
        <dc:language>de</dc:language>
        <meta property="dcterms:modified">${new Date().toISOString()}</meta>
    </metadata>
    <manifest>
        <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
        <item id="css" href="styles.css" media-type="text/css"/>
        ${manifestItems}
    </manifest>
    <spine>
        <itemref idref="nav"/>
        ${spineItems}
    </spine>
</package>`);

    // CSS für E-Reader - Style für nicht-klickbare interne Links
    oebpsFolder.file("styles.css", `
body {
    font-family: serif;
    line-height: 1.6;
    margin: 1em;
}
h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    line-height: 1.2;
}
h1 {
    font-size: 1.8em;
    border-bottom: 2px solid #333;
    padding-bottom: 0.3em;
}
p {
    margin-bottom: 1em;
    text-align: justify;
}
nav[epub\\:type="toc"] ol {
    list-style-type: none;
    padding-left: 1em;
}
nav[epub\\:type="toc"] ol ol {
    padding-left: 2em;
}
.internal-link-static {
    font-style: italic;
    color: #555;
}
a {
    color: #0000ee;
    text-decoration: underline;
}
code {
    font-family: monospace;
    background-color: #f5f5f5;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}
pre {
    background-color: #f5f5f5;
    padding: 1em;
    border-radius: 5px;
    overflow-x: auto;
    white-space: pre-wrap;
}
blockquote {
    margin: 1em 0;
    padding-left: 1em;
    border-left: 3px solid #ccc;
    font-style: italic;
}
ul, ol {
    margin-bottom: 1em;
    padding-left: 2em;
}
`);

    // SCHRITT 3: Kapitel generieren.
    nodes.forEach((node, index) => {
        const sanitizedTitle = node.title.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const chapterContent = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>${sanitizedTitle}</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
    <h1>${sanitizedTitle}</h1>
    ${marked(node.content || '')}
</body>
</html>`;

        oebpsFolder.file(`chapter${index + 1}.xhtml`, chapterContent);
    });

    // EPUB downloaden
    const content = await zip.generateAsync({type: "blob", mimeType: "application/epub+zip"});
    const url = URL.createObjectURL(content);
    const a = document.createElement('a');
    a.href = url;
    a.download = `knowledge-base-export-${new Date().toISOString().split('T')[0]}.epub`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

const SecureImage = ({ src, alt, ...props }) => {
    const [imageSrc, setImageSrc] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        // Zustand zurücksetzen, wenn sich die src ändert
        setImageSrc(null);
        setError(null);
        
        // Abbruch-Controller für den Fall, dass die Komponente unmounted wird,
        // während der Fetch noch läuft.
        const abortController = new AbortController();

        const fetchImage = async () => {
            if (!src) return;
            try {
                // Wichtig: 'blob' als responseType angeben!
                const response = await api.get(src, {
                    responseType: 'blob',
                    signal: abortController.signal,
                });
                // Erstelle eine temporäre, lokale URL aus den binären Bilddaten (Blob)
                const objectURL = URL.createObjectURL(response.data);
                setImageSrc(objectURL);
            } catch (err) {
                if (err.name !== 'CanceledError') {
                    console.error("Failed to load secure image:", err);
                    setError("Could not load image.");
                }
            }
        };

        fetchImage();

        // Cleanup-Funktion: Widerruft die Object-URL, um Speicher freizugeben
        // und bricht den Fetch ab, falls er noch läuft.
        return () => {
            abortController.abort();
            if (imageSrc) {
                URL.revokeObjectURL(imageSrc);
            }
        };
    }, [src]); // Effekt erneut ausführen, wenn sich die `src` ändert

    if (error) {
        return <span className="image-error" {...props}>{alt || 'Image failed to load'}</span>;
    }

    if (!imageSrc) {
        return <span className="image-loading" {...props}>{alt || 'Loading image...'}</span>;
    }

    return <img src={imageSrc} alt={alt} {...props} />;
};

/**
 * Durchläuft den Baum und gibt die ausgewählten Nodes als strukturiertes
 * Array für ein Inhaltsverzeichnis zurück.
 */
const generateTocForSelectedNodes = (nodes, selectedIds) => {
    const toc = [];
    const traverse = (node, level) => {
        // Füge den Node zum ToC hinzu, wenn er ausgewählt ist
        if (selectedIds.has(node.id)) {
            toc.push({ id: node.id, title: node.title, level: level });
        }

        // Durchlaufe immer die Kinder, da ein Kind ausgewählt sein könnte,
        // auch wenn der Eltern-Node es nicht ist.
        if (node.children) {
            // Wichtig: Das Level für die Kinder nur erhöhen, wenn der Parent auch im ToC ist.
            // Ansonsten behalten wir das Level bei, um die relative Hierarchie zu wahren.
            const newLevel = selectedIds.has(node.id) ? level + 1 : level;
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

/**
 * Durchläuft den Baum und gibt die ausgewählten Node-IDs in ihrer visuellen Reihenfolge zurück.
 */
const getIdsInOrder = (nodes, idsToFind) => {
    let orderedIds = [];
    const traverse = (node) => {
        if (idsToFind.has(node.id)) {
            orderedIds.push(node.id);
        }
        if (node.children) {
            for (const child of node.children) {
                traverse(child);
            }
        }
    };
    for (const rootNode of nodes) {
        traverse(rootNode);
    }
    return orderedIds;
};

/**
 * Die Komponente, die einen einzelnen Node im Baum darstellt.
 * Inklusive Drag-and-Drop-Funktionalität und Checkboxen.
 */
function TreeNode({ node, activeNodeId, moveNode, onNodeClick, onAddNode, onDeleteNode, collapsedNodes, onToggleCollapse }) {
    const ref = useRef(null);
    const { selectedNodeIds, toggleNodeSelection } = useAppContext();

    const [{ isDragging }, drag] = useDrag({
        type: 'NODE',
        item: () => ({ node }),
        collect: (monitor) => ({ isDragging: monitor.isDragging() }),
    });

    const [, drop] = useDrop({
        accept: 'NODE',
        drop: (item) => {
            if (item.node.id !== node.id && item.node.parentId !== node.id) {
                moveNode(item.node, node);
            }
        },
    });

    drag(drop(ref));
    const isCollapsed = collapsedNodes.has(node.id);

    return (
        <div ref={ref} style={{ opacity: isDragging ? 0.5 : 1 }}>
            <TreeView
                nodeLabel={
                    <div className="node-label">
                        <input
                            type="checkbox"
                            className="node-checkbox"
                            checked={selectedNodeIds.has(node.id)}
                            onChange={(e) => { e.stopPropagation(); toggleNodeSelection(node.id); }}
                            onClick={(e) => e.stopPropagation()}
                        />
                        <span className="node-title" onClick={() => onNodeClick(node)}>
                            {node.title}
                        </span>
                        <span className="node-controls">
                            <span className="control-icon" onClick={(e) => { e.stopPropagation(); onAddNode(node); }}>+</span>
                            <span className="control-icon" onClick={(e) => { e.stopPropagation(); onDeleteNode(node); }}>-</span>
                        </span>
                    </div>
                }
                collapsed={isCollapsed}
                onClick={() => onToggleCollapse(node.id)}
            >
                {node.children?.map((childNode) => (
                    <TreeNode
                        key={childNode.id}
                        node={childNode}
                        activeNodeId={activeNodeId}
                        moveNode={moveNode}
                        onNodeClick={onNodeClick}
                        onAddNode={onAddNode}
                        onDeleteNode={onDeleteNode}
                        collapsedNodes={collapsedNodes}
                        onToggleCollapse={onToggleCollapse}
                    />
                ))}
            </TreeView>
        </div>
    );
}

/**
 * Die rechte Seitenleiste mit Kontext-Aktionen (Kopieren, Drucken) und dem Chat.
 */
const ContextPanel = () => {
    // NEU: setSelectedNodeIds aus dem Context holen
    const { selectedNodeIds, setSelectedNodeIds, getContextContent, treeData, enterPrintPreview } = useAppContext();

    const [contextTitles, setContextTitles] = useState([]);
    const [isCopyingContent, setIsCopyingContent] = useState(false);
    const [copyContentSuccess, setCopyContentSuccess] = useState('');
    const [isCopyingTree, setIsCopyingTree] = useState(false);
    const [copyTreeSuccess, setCopyTreeSuccess] = useState('');
    const [isPrinting, setIsPrinting] = useState(false);
    const [isExporting, setIsExporting] = useState(false);
    const [isExportingMd, setIsExportingMd] = useState(false);

    // NEU: State für die gespeicherten Auswahlen
    const [savedSelections, setSavedSelections] = useState({});
    const [selectedSaveName, setSelectedSaveName] = useState('');

    // Beim ersten Laden die Auswahlen aus dem localStorage holen
    useEffect(() => {
        try {
            const stored = localStorage.getItem('knowledgeBaseSelections');
            if (stored) {
                setSavedSelections(JSON.parse(stored));
            }
        } catch (error) {
            console.error("Could not load selections from localStorage", error);
            setSavedSelections({});
        }
    }, []);

    useEffect(() => {
        const fetchTitles = async () => {
            if (selectedNodeIds.size > 0) {
                const { titles } = await getContextContent();
                setContextTitles(titles);
            } else {
                setContextTitles([]);
            }
        };
        fetchTitles();
    }, [selectedNodeIds, getContextContent]);

    // NEU: Funktion zum Speichern der aktuellen Auswahl
    const handleSaveSelection = useCallback(() => {
        if (selectedNodeIds.size === 0) {
            alert("Please select at least one node to save the selection.");
            return;
        }
        const name = prompt("Enter a name for this selection:");
        if (!name || !name.trim()) {
            return;
        }

        const newSelections = {
            ...savedSelections,
            [name.trim()]: Array.from(selectedNodeIds) // Set in Array umwandeln für JSON
        };

        setSavedSelections(newSelections);
        localStorage.setItem('knowledgeBaseSelections', JSON.stringify(newSelections));
        alert(`Selection "${name.trim()}" saved!`);
    }, [selectedNodeIds, savedSelections]);

    // NEU: Funktion zum Laden einer gespeicherten Auswahl
    const handleLoadSelection = useCallback(() => {
        if (!selectedSaveName || !savedSelections[selectedSaveName]) {
            alert("Please select a saved selection to load.");
            return;
        }
        const idsToLoad = savedSelections[selectedSaveName];
        setSelectedNodeIds(new Set(idsToLoad)); // Array aus localStorage in Set umwandeln
    }, [selectedSaveName, savedSelections, setSelectedNodeIds]);
    
    // NEU: Funktion zum Löschen einer gespeicherten Auswahl
    const handleDeleteSelection = useCallback(() => {
        if (!selectedSaveName || !savedSelections[selectedSaveName]) {
            alert("Please select a saved selection to delete.");
            return;
        }
        if (window.confirm(`Are you sure you want to delete the selection "${selectedSaveName}"?`)) {
            const newSelections = { ...savedSelections };
            delete newSelections[selectedSaveName];
            
            setSavedSelections(newSelections);
            localStorage.setItem('knowledgeBaseSelections', JSON.stringify(newSelections));
            setSelectedSaveName(''); // Auswahl im Dropdown zurücksetzen
            alert(`Selection "${selectedSaveName}" deleted.`);
        }
    }, [selectedSaveName, savedSelections]);


    const handleCopyContext = useCallback(async () => {
        // ... (unverändert)
        setIsCopyingContent(true);
        setCopyContentSuccess('');
        const { content } = await getContextContent();
        if (content) {
            navigator.clipboard.writeText(content)
                .then(() => setCopyContentSuccess('Content Copied!'))
                .catch(() => setCopyContentSuccess('Failed.'));
        } else {
            setCopyContentSuccess('Nothing to copy.');
        }
        setTimeout(() => setCopyContentSuccess(''), 2000);
        setIsCopyingContent(false);
    }, [getContextContent]);

    const handleCopyTree = useCallback(async () => {
        // ... (unverändert)
        if (!treeData || treeData.length === 0) {
            setCopyTreeSuccess('Tree not loaded.');
            setTimeout(() => setCopyTreeSuccess(''), 2000);
            return;
        }
        setIsCopyingTree(true);
        setCopyTreeSuccess('');
        const formatNode = (node, level = 0) => {
            const indent = '  '.repeat(level);
            let output = `${indent}- ${node.title}\n`;
            if (node.children?.length > 0) {
                output += node.children.map(child => formatNode(child, level + 1)).join('');
            }
            return output;
        };
        const formattedTree = treeData.map(rootNode => formatNode(rootNode, 0)).join('');
        try {
            await navigator.clipboard.writeText(formattedTree);
            setCopyTreeSuccess('Tree Copied!');
        } catch (err) {
            setCopyTreeSuccess('Failed.');
        }
        setTimeout(() => setCopyTreeSuccess(''), 2000);
        setIsCopyingTree(false);
    }, [treeData]);

	const handlePrintSelection = useCallback(async () => {
		// ... (unverändert)
		if (selectedNodeIds.size === 0) {
			alert("Please select at least one node from the tree to print.");
			return;
		}
		setIsPrinting(true);
		try {
			const toc = generateTocForSelectedNodes(treeData, selectedNodeIds);
			const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
			const nodePromises = orderedIds.map(id => api.get(`/api/nodes/${id}`));
			const nodeResponses = await Promise.all(nodePromises);
			const foundNodes = nodeResponses.map(res => res.data);
			enterPrintPreview({ nodes: foundNodes, toc: toc });
		} catch (err) {
			console.error("Failed to fetch nodes for printing:", err);
		} finally {
			setIsPrinting(false);
		}
	}, [selectedNodeIds, treeData, enterPrintPreview]);

    const handleExportEpub = useCallback(async () => {
        // ... (unverändert)
        if (selectedNodeIds.size === 0) {
            alert("Please select at least one node to export.");
            return;
        }
        setIsExporting(true);
        try {
            const toc = generateTocForSelectedNodes(treeData, selectedNodeIds);
            const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
            const nodePromises = orderedIds.map(id => api.get(`/api/nodes/${id}`));
            const nodeResponses = await Promise.all(nodePromises);
            const foundNodes = nodeResponses.map(res => res.data);
            await generateEpub(foundNodes, toc);
        } catch (err) {
            console.error("Failed to export EPUB:", err);
            alert("An error occurred during EPUB export. See console for details.");
        } finally {
            setIsExporting(false);
        }
    }, [selectedNodeIds, treeData]);

    const handleExportMarkdown = useCallback(async () => {
        // ... (unverändert)
        if (selectedNodeIds.size === 0) {
            alert("Please select at least one node to export.");
            return;
        }
        setIsExportingMd(true);
        try {
            const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
            const nodePromises = orderedIds.map(id => api.get(`/api/nodes/${id}`));
            const nodeResponses = await Promise.all(nodePromises);
            const foundNodes = nodeResponses.map(res => res.data);
            const markdownContent = foundNodes.map(node => {
                return `# ${node.title}\n\n${node.content || ''}`;
            }).join('\n\n---\n\n');
            const blob = new Blob([markdownContent], { type: 'text/markdown;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.download = `knowledge-base-export-${new Date().toISOString().split('T')[0]}.md`;
            a.href = url;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error("Failed to export Markdown:", err);
            alert("An error occurred during Markdown export. See console for details.");
        } finally {
            setIsExportingMd(false);
        }
    }, [selectedNodeIds, treeData]);

    return (
        <div className="context-panel-container">
            <div className="context-selection-area">
                <h3>Context Actions</h3>
                
                {/* NEUE UI ZUM SPEICHERN/LADEN */}
                <div className="selection-management">
                    <h4>Manage Selections</h4>
                    <div className="selection-controls">
                        <select 
                            value={selectedSaveName} 
                            onChange={(e) => setSelectedSaveName(e.target.value)}
                            className="selection-dropdown"
                        >
                            <option value="">-- Load a selection --</option>
                            {Object.keys(savedSelections).sort().map(name => (
                                <option key={name} value={name}>{name}</option>
                            ))}
                        </select>
                        <button onClick={handleLoadSelection} disabled={!selectedSaveName} className="btn btn-sm btn-info">Load</button>
                        <button onClick={handleDeleteSelection} disabled={!selectedSaveName} className="btn btn-sm btn-danger">Del</button>
                    </div>
                    <button onClick={handleSaveSelection} className="btn btn-sm btn-secondary btn-block">Save Current Selection</button>
                </div>

                <div className="context-selection-list">
                    <h4>Currently Selected ({selectedNodeIds.size})</h4>
                    {contextTitles.length > 0 ? (
                        <ul>{contextTitles.map((title, index) => <li key={index}>{title}</li>)}</ul>
                    ) : (
                        <p className="no-context-message">Select nodes to build your context.</p>
                    )}
                </div>
                <div className="context-actions">
					<button onClick={handleCopyContext} disabled={isCopyingContent || selectedNodeIds.size === 0} className="btn btn-secondary">
						{isCopyingContent ? 'Copying...' : 'Copy Content'}
					</button>
					<button onClick={handleCopyTree} disabled={isCopyingTree || !treeData || treeData.length === 0} className="btn btn-secondary">
						{isCopyingTree ? 'Copying...' : 'Copy Tree'}
					</button>
					<button onClick={handlePrintSelection} disabled={isPrinting || selectedNodeIds.size === 0} className="btn btn-success">
						{isPrinting ? 'Preparing...' : `Print Selection`}
					</button>
					<button onClick={handleExportEpub} disabled={isExporting || selectedNodeIds.size === 0} className="btn btn-primary">
						{isExporting ? 'Exporting...' : `Export EPUB`}
					</button>
					<button onClick={handleExportMarkdown} disabled={isExportingMd || selectedNodeIds.size === 0} className="btn btn-secondary">
						{isExportingMd ? 'Exporting...' : 'Export Markdown'}
					</button>
				</div>
                <div className="copy-success-area">
                    {copyContentSuccess && <span className="copy-success">{copyContentSuccess}</span>}
                    {copyTreeSuccess && <span className="copy-success">{copyTreeSuccess}</span>}
                </div>
            </div>
            <div className="chat-container">
                <Chat />
            </div>
        </div>
    );
};

// #endregion

// ============================================================================
// #region MAIN COMPONENT: NodeEdit
// ============================================================================

function NodeEdit() {
    const { nodeId } = useParams();
    const navigate = useNavigate();
    const { setTreeDataForContext, isPrintPreviewActive, exitPrintPreview } = useAppContext();

    // #region State Management
    const [treeData, setTreeData] = useState([]);
    const [currentNode, setCurrentNode] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editableContent, setEditableContent] = useState('');
    const [selectedVersion, setSelectedVersion] = useState(null);
    const [successMessage, setSuccessMessage] = useState('');
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [nodeToDelete, setNodeToDelete] = useState(null);
    const [isVersionHistoryVisible, setIsVersionHistoryVisible] = useState(true);
    const [collapsedNodes, setCollapsedNodes] = useState(new Set());
    // #endregion

    // #region Side Effects
    // Steuert die Body-Klasse, um den Druckmodus zu aktivieren/deaktivieren.
    useEffect(() => {
        if (isPrintPreviewActive) {
            document.body.classList.add('print-preview-active');
        } else {
            document.body.classList.remove('print-preview-active');
        }
        // WICHTIG: Cleanup-Funktion, um die Klasse sicher zu entfernen
        return () => {
            document.body.classList.remove('print-preview-active');
        };
    }, [isPrintPreviewActive]);

    // Lädt die initialen Daten für den Baum und den aktuell ausgewählten Node.
    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            setError(null);
            setSuccessMessage('');
            try {
                const treePromise = api.get('/api/nodes/tree');
                if (nodeId) {
                    const nodePromise = api.get(`/api/nodes/${nodeId}`);
                    const [treeResponse, nodeResponse] = await Promise.all([treePromise, nodePromise]);
                    setTreeData(treeResponse.data);
                    setTreeDataForContext(treeResponse.data);
                    setCurrentNode(nodeResponse.data);
                    setEditableContent(nodeResponse.data.content);
                    setIsEditing(false);
                    setSelectedVersion(null);
                } else {
                    const treeResponse = await treePromise;
                    setTreeData(treeResponse.data);
                    setTreeDataForContext(treeResponse.data);
                    setCurrentNode(null);
                }
            } catch (err) {
                console.error("Failed to fetch data:", err);
                setError("Could not load knowledge base. Please try again.");
                setCurrentNode(null);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, [nodeId, setTreeDataForContext]);

    // Timer für Erfolgsmeldungen
    useEffect(() => {
        if (successMessage) {
            const timer = setTimeout(() => setSuccessMessage(''), 3000);
            return () => clearTimeout(timer);
        }
    }, [successMessage]);
    // #endregion

    // #region Handlers & Logic
    const toggleNodeCollapse = (nodeIdToToggle) => {
        setCollapsedNodes(prevSet => {
            const newSet = new Set(prevSet);
            if (newSet.has(nodeIdToToggle)) {
                newSet.delete(nodeIdToToggle);
            } else {
                newSet.add(nodeIdToToggle);
            }
            return newSet;
        });
    };

    const refreshTree = async () => {
        const response = await api.get('/api/nodes/tree');
        setTreeData(response.data);
        setTreeDataForContext(response.data);
    };

    const handleNodeClick = (node) => navigate(`/nodes/${node.id}`);
    const handleAddNode = async (parentNode) => {
        const title = prompt("Enter the title for the new node:");
        if (!title) return;
        try {
            const response = await api.post('/api/nodes', { title, parent_id: parentNode.id });
            await refreshTree();
            navigate(`/nodes/${response.data.id}`);
        } catch (err) {
            setError("Could not create node.");
        }
    };
    const handleDeleteNode = (node) => {
        if (node.title === 'IFS Landkarte') {
            alert('This special node cannot be deleted.');
            return;
        }
        setNodeToDelete(node);
        setIsDeleteModalOpen(true);
    };
    const executeDelete = async () => {
        if (!nodeToDelete) return;
        try {
            await api.delete(`/api/nodes/${nodeToDelete.id}`);
            await refreshTree();
            if (nodeId === String(nodeToDelete.id)) {
                navigate(nodeToDelete.parentId ? `/nodes/${nodeToDelete.parentId}` : '/');
            }
            setSuccessMessage(`Node "${nodeToDelete.title}" was successfully deleted.`);
        } catch (err) {
            setError("Could not delete node. It might have children.");
        } finally {
            setIsDeleteModalOpen(false);
            setNodeToDelete(null);
        }
    };
    const cancelDelete = () => {
        setIsDeleteModalOpen(false);
        setNodeToDelete(null);
    };
    const moveNode = async (sourceNode, targetParentNode) => {
        try {
            await api.post('/api/nodes/move', { node_id: sourceNode.id, new_parent_id: targetParentNode.id });
            await refreshTree();
        } catch (err) {
            setError("Could not move the node.");
        }
    };
    const handleSave = async () => {
        if (!currentNode) return;
        try {
            const response = await api.put(`/api/nodes/${currentNode.id}`, { content: editableContent, title: currentNode.title });
            setCurrentNode(response.data);
            setEditableContent(response.data.content);
            setIsEditing(false);
            setSelectedVersion(null);
            setSuccessMessage("Saved successfully!");
        } catch (err) {
            setError("Could not save the node.");
        }
    };
    const handleVersionClick = (version) => {
        setSelectedVersion(version);
        setEditableContent(version.content);
        setIsEditing(false);
    };
    const handleRename = async () => {
        if (!currentNode) return;
        const newTitle = prompt("Enter the new title for the node:", currentNode.title);
        if (!newTitle || !newTitle.trim() || newTitle.trim() === currentNode.title) {
            return;
        }
        try {
            const response = await api.patch(`/api/nodes/${currentNode.id}/rename`, { title: newTitle.trim() });
            setCurrentNode(prevNode => ({ ...prevNode, title: response.data.title }));
            await refreshTree();
            setSuccessMessage("Node renamed successfully!");
        } catch (err) {
            setError("Could not rename the node.");
        }
    };
    const handleLinkClick = async (linkText) => {
        try {
            const response = await api.get('/api/nodes', { params: { title: linkText.trim() } });
            const results = response.data;
            if (Array.isArray(results) && results.length > 0) {
                const nodeData = results[0];
                if (nodeData && nodeData.id) {
                    navigate(`/nodes/${nodeData.id}`);
                } else {
                    setError(`Found a node for "${linkText}" but it has an invalid format.`);
                }
            } else {
                setError(`Link target "${linkText}" does not exist.`);
            }
        } catch (error) {
            console.error('Error fetching node by title:', error);
            setError(`Could not follow link to "${linkText}". An error occurred.`);
        }
    };

    const renderTextWithLinks = (children) => {
        return React.Children.map(children, child => {
            if (typeof child === 'string') {
                const linkRegex = /\[\[\s*([^|\]\s][^|\]]*?)\s*(?:\|\s*(.+?)\s*)?\]\]/g;
                const parts = [];
                let lastIndex = 0;
                const matches = [...child.matchAll(linkRegex)];
                if (matches.length === 0) { return child; }
                matches.forEach((match, index) => {
                    const [fullMatch, target, displayText] = match;
                    const matchIndex = match.index;
                    if (matchIndex > lastIndex) {
                        parts.push(child.substring(lastIndex, matchIndex));
                    }
                    parts.push(
                        <span key={`${target}-${index}`} onClick={() => handleLinkClick(target)} className="internal-link" role="button" tabIndex={0}>
                            {displayText || target}
                        </span>
                    );
                    lastIndex = matchIndex + fullMatch.length;
                });
                if (lastIndex < child.length) {
                    parts.push(child.substring(lastIndex));
                }
                return parts;
            }
            if (React.isValidElement(child) && child.props.children) {
                return React.cloneElement(child, { children: renderTextWithLinks(child.props.children) });
            }
            return child;
        });
    };
    // #endregion

    // #region Conditional Rendering
    const PrintPreview = () => {
        const { printPreviewData } = useAppContext();
        const { nodes, toc } = printPreviewData || { nodes: [], toc: [] };

        const previewContent = (
            <div className="print-preview-overlay">
                <div className="print-preview-container">
                    <div className="print-preview-header">
                        <p>Print Preview ({nodes.length} nodes)</p>
                        <div>
                            <button className="btn btn-primary" onClick={() => window.print()}>Print (Ctrl+P)</button>
                            <button className="btn btn-secondary" onClick={exitPrintPreview}>Exit Preview</button>
                        </div>
                    </div>

                    {toc && toc.length > 0 && (
                        <div className="print-toc">
                            <h2>Inhaltsverzeichnis</h2>
                            <ul>
                                {toc.map(item => (
                                    <li
                                        key={item.id}
                                        style={{ paddingLeft: `${item.level * 20}px` }}
                                    >
                                        <a href={`#print-node-${item.id}`}>{item.title}</a>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {nodes.map(node => (
                        <div key={node.id} id={`print-node-${node.id}`} className="print-node">
                            <h1>{node.title}</h1>
                            <div className="view-content">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={{
                                            p: ({ node, ...props }) => <p {...props}>{renderTextWithLinks(props.children)}</p>,
                                            li: ({ node, ...props }) => <li {...props}>{renderTextWithLinks(props.children)}</li>,
                                            h1: ({ node, ...props }) => <h1 {...props}>{renderTextWithLinks(props.children)}</h1>,
                                            h2: ({ node, ...props }) => <h2>{renderTextWithLinks(props.children)}</h2>,
                                            h3: ({ node, ...props }) => <h3>{renderTextWithLinks(props.children)}</h3>,
                                            h4: ({ node, ...props }) => <h4>{renderTextWithLinks(props.children)}</h4>,
                                            h5: ({ node, ...props }) => <h5>{renderTextWithLinks(props.children)}</h5>,
                                            h6: ({ node, ...props }) => <h6>{renderTextWithLinks(props.children)}</h6>,
											img: SecureImage,
                                        }}
                                    >
                                        {node.content || ''}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            );
        return ReactDOM.createPortal(previewContent, document.body);
    };

    if (isLoading) return <div className="centered-message">Loading Knowledge Base...</div>;
    if (error) return <div className="centered-message error-message">Error: {error}</div>;

    if (isPrintPreviewActive) {
        return <PrintPreview />;
    }
    // #endregion

    return (
        <DndProvider backend={HTML5Backend}>
            <div className="node-edit-layout">
                {/* Pane 1: Tree View */}
                <div className="tree-view-pane">
                    <div className="tree-node-list">
                        {treeData.map((rootNode) => (
                            <TreeNode key={rootNode.id} node={rootNode} activeNodeId={String(nodeId)} moveNode={moveNode} onNodeClick={handleNodeClick} onAddNode={handleAddNode} onDeleteNode={handleDeleteNode} collapsedNodes={collapsedNodes} onToggleCollapse={toggleNodeCollapse} />
                        ))}
                    </div>
                </div>

                {/* Pane 2: Content View */}
                <div className="node-content-pane">
                    {currentNode ? (
                        currentNode.title === 'IFS Landkarte' ? (
                            <IFSLandkarte onLinkClick={handleLinkClick} />
                        ) : (
                            <>
                                <div className="main-content-header">
                                    <h1>{currentNode.title}</h1>
                                    <div className="action-buttons">
                                        {!isEditing && (
                                            <>
                                                <button className="btn btn-secondary" onClick={handleRename}>Rename</button>
                                                <button className="btn btn-primary" onClick={() => setIsEditing(true)}>Edit</button>
                                            </>
                                        )}
                                        <button className="btn btn-secondary btn-toggle" onClick={() => setIsVersionHistoryVisible(!isVersionHistoryVisible)}>
                                            {isVersionHistoryVisible ? 'Hide Versions' : 'Show Versions'}
                                        </button>
                                    </div>
                                </div>

                                {successMessage && <div className="success-message">{successMessage}</div>}

                                <div className="content-and-versions-wrapper">
                                    <div className="main-content-area">
                                        <div className="content-area">
                                            {isEditing ? (
                                                <>
                                                    <textarea className="edit-textarea" value={editableContent} onChange={(e) => setEditableContent(e.target.value)} />
                                                    <div className="edit-buttons">
                                                        <button className="btn btn-primary" onClick={handleSave}>Save</button>
                                                        <button className="btn btn-secondary" onClick={() => { setIsEditing(false); setEditableContent(currentNode.content); }}>Cancel</button>
                                                    </div>
                                                </>
                                            ) : (
                                                <div className="view-content">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ p: ({ node, ...props }) => <p {...props}>{renderTextWithLinks(props.children)}</p>, li: ({ node, ...props }) => <li {...props}>{renderTextWithLinks(props.children)}</li>, h1: ({ node, ...props }) => <h1 {...props}>{renderTextWithLinks(props.children)}</h1>, h2: ({ node, ...props }) => <h2>{renderTextWithLinks(props.children)}</h2>, h3: ({ node, ...props }) => <h3>{renderTextWithLinks(props.children)}</h3>, h4: ({ node, ...props }) => <h4>{renderTextWithLinks(props.children)}</h4>, h5: ({ node, ...props }) => <h5>{renderTextWithLinks(props.children)}</h5>, h6: ({ node, ...props }) => <h6>{renderTextWithLinks(props.children)}</h6>,img: SecureImage, }}>
                                                        {selectedVersion ? selectedVersion.content : currentNode.content}
                                                    </ReactMarkdown>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {isVersionHistoryVisible && (
                                        <div className="version-history-panel">
                                            <h2>Version History</h2>
                                            {selectedVersion && (
                                                <button onClick={() => { setSelectedVersion(null); setEditableContent(currentNode.content); }}>Show Current Version</button>
                                            )}
                                            <ul>
                                                {(currentNode.versions || []).slice().reverse().map((v) => (
                                                    <li key={v.id || v.timestamp} onClick={() => handleVersionClick(v)} className={selectedVersion?.id === v.id || selectedVersion?.timestamp === v.timestamp ? 'selected' : ''}>
                                                        Version from {new Date(v.timestamp).toLocaleString()}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            </>
                        )
                    ) : (
                        <div className="splash-page">
                            <h1>Welcome to Your Knowledge Base</h1>
                            <p>Select a node from the tree on the left to begin.</p>
                        </div>
                    )}
                </div>

                {/* Pane 3: Context Panel */}
                <div className="context-pane">
                    <ContextPanel />
                </div>
            </div>

            <Modal isOpen={isDeleteModalOpen} onRequestClose={cancelDelete} contentLabel="Confirm Deletion" className="modal" overlayClassName="modal-overlay">
                <h2>Confirm Deletion</h2>
                {nodeToDelete && <p>Are you sure you want to delete the node "<strong>{nodeToDelete.title}</strong>"?</p>}
                <p>This action cannot be undone.</p>
                <div className="modal-buttons">
                    <button className="btn btn-danger" onClick={executeDelete}>Delete</button>
                    <button className="btn btn-secondary" onClick={cancelDelete}>Cancel</button>
                </div>
            </Modal>
        </DndProvider>
    );
}

export default NodeEdit;
// #endregion
