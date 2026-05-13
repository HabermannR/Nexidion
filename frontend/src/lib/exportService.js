// src/services/exportService.js

import { marked } from 'marked';
import { getIdsInOrder, generateTocForSelectedNodes } from '../features/nodes/node.utils.js'; // Importieren die Helfer
import api from '../api/apiClient.js';

// Die komplette, riesige generateEpub Funktion hier einfügen
// Korrigierte generateEpub Funktion mit XML-Entitäten und vollständiger Bildunterstützung
// WICHTIG: Du musst 'api' aus '../api/axios' importieren!

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
    const imagesFolder = oebpsFolder.folder("images"); // Ordner für Bilder

    // Hilfsfunktion für XML-Escaping
    const escapeXml = (text) => {
        return text.replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;')
                  .replace(/'/g, '&apos;');
    };

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

            // Füge das aktuelle Element hinzu - KORREKTE XML-ENTITÄTEN
            html += `<li><a href="${chapterFilename}">${escapeXml(item.title)}</a>`;
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

    // Sammle alle Bilder aus dem Content und lade sie über die API
    // Sammle alle Bilder aus dem Content und lade sie über die API
const imageFiles = new Map(); // Map: filename -> blob data
 const loadImageWithFallback = async (basePath) => {
        const lastDotIndex = basePath.lastIndexOf('.');
        const swImagePath = lastDotIndex === -1
            ? `${basePath}_sw`
            : `${basePath.substring(0, lastDotIndex)}_sw${basePath.substring(lastDotIndex)}`;
        
        // VERSUCH 1: Lade die _sw-Version
        try {
            const response = await api.get(swImagePath, { responseType: 'blob' });
            return { blob: response.data, contentType: response.headers['content-type'] || response.data.type };
        } catch (swError) {
            // Wenn _sw-Version fehlschlägt, ist das okay, wir versuchen das Original.
            console.log(`SW-version for ${basePath} not found, trying original.`);
        }

        // VERSUCH 2: Lade die Original-Version
        try {
            const response = await api.get(basePath, { responseType: 'blob' });
            return { blob: response.data, contentType: response.headers['content-type'] || response.data.type };
        } catch (originalError) {
            // Wenn auch das Original fehlschlägt, geben wir einen klaren Fehler aus und werfen ihn.
            console.error(`Failed to load image (both SW and original): ${basePath}`, originalError);
            throw new Error(`Could not load image: ${basePath}`);
        }
    };


    const processImagesInContent = async (content) => {
        const imgRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
        let processedContent = content;
        // WICHTIG: `map` mit `Promise.all` verwenden, um parallel zu laden
        const matches = [...content.matchAll(imgRegex)];
        
        for (const match of matches) {
            const [fullMatch, altText, imagePath] = match;
            
            try {
                // Lade das Bild mit der neuen, robusten Funktion
                let { blob: imageBlob, contentType } = await loadImageWithFallback(imagePath);
                
                // SVG-Sonderbehandlung (bleibt gleich, aber jetzt mit korrekten Daten)
                if (contentType && contentType.includes('svg')) {
                    // ... (deine bestehende SVG-Logik hier einfügen)
                    const svgResponse = await api.get(imagePath, { responseType: 'text' });
                    let svgContent = svgResponse.data;
                    const svgMatch = svgContent.match(/<svg[^>]*>[\s\S]*?<\/svg>/i);
                    if (svgMatch) svgContent = svgMatch[0];
                    imageBlob = new Blob([svgContent], { type: 'image/svg+xml' });
                }
                
                const filename = `image_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                const extension = imagePath.split('.').pop().toLowerCase() || 'jpg';
                const fullFilename = `${filename}.${extension}`;
                
                imageFiles.set(fullFilename, imageBlob);
                
                const htmlImg = `<img src="images/${fullFilename}" alt="${escapeXml(altText)}" style="max-width: 100%; height: auto;"/>`;
                processedContent = processedContent.replace(fullMatch, htmlImg);
                
            } catch (error) {
                // Dieser Catch-Block wird jetzt nur noch erreicht, wenn BEIDE Ladeversuche fehlschlagen.
                console.warn(error.message); // Zeigt z.B. "Could not load image: /path/to/image.jpg"
                const fallback = `<em class="image-placeholder">[Bild: ${escapeXml(altText || imagePath)}]</em>`;
                processedContent = processedContent.replace(fullMatch, fallback);
            }
        }
        
        return processedContent;
    };

    // content.opf (Manifest) - Aktualisiert für EPUB 3
    const manifestItems = nodes.map((node, index) =>
        `<item id="chapter${index + 1}" href="chapter${index + 1}.xhtml" media-type="application/xhtml+xml"/>`
    ).join('\n    ');

    // Füge Bild-Items zum Manifest hinzu
    const imageManifestItems = Array.from(imageFiles.keys()).map(filename => {
        const extension = filename.split('.').pop().toLowerCase();
        let mediaType = 'image/jpeg'; // Standard
        if (extension === 'png') mediaType = 'image/png';
        else if (extension === 'gif') mediaType = 'image/gif';
        else if (extension === 'svg') mediaType = 'image/svg+xml';
        else if (extension === 'webp') mediaType = 'image/webp';
        
        const itemId = `img-${filename.replace(/[^a-zA-Z0-9]/g, '-')}`;
        return `<item id="${itemId}" href="images/${filename}" media-type="${mediaType}"/>`;
    }).join('\n    ');

    const spineItems = nodes.map((node, index) =>
        `<itemref idref="chapter${index + 1}"/>`
    ).join('\n    ');

    const bookTitle = "Knowledge Base Export";
    const bookId = `kb-export-${Date.now()}`;

    oebpsFolder.file("content.opf", `<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>${escapeXml(bookTitle)}</dc:title>
        <dc:creator>Knowledge Base</dc:creator>
        <dc:identifier id="bookid">${bookId}</dc:identifier>
        <dc:language>de</dc:language>
        <meta property="dcterms:modified">${new Date().toISOString()}</meta>
    </metadata>
    <manifest>
        <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
        <item id="css" href="styles.css" media-type="text/css"/>
        ${manifestItems}
        ${imageManifestItems}
    </manifest>
    <spine>
        <itemref idref="nav"/>
        ${spineItems}
    </spine>
</package>`);

    // CSS für E-Reader - Style für nicht-klickbare interne Links + Bilder
    // CSS für E-Reader - Style für nicht-klickbare interne Links + Bilder
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
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
    page-break-inside: avoid;
}
/* Spezielle Regeln für SVG-Bilder in EPUB */
img[src$=".svg"] {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
    page-break-inside: avoid;
}
.image-placeholder {
    color: #999;
    font-style: italic;
    background: #f5f5f5;
    padding: 0.5em;
    border-radius: 3px;
    display: inline-block;
}
`);

    // SCHRITT 3: Kapitel generieren mit Bildverarbeitung (ASYNC!)
    for (let index = 0; index < nodes.length; index++) {
        const node = nodes[index];
        const sanitizedTitle = escapeXml(node.title);
        const processedContent = await processImagesInContent(node.content || '');
        
        const chapterContent = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>${sanitizedTitle}</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
    <h1>${sanitizedTitle}</h1>
    ${marked(processedContent)}
</body>
</html>`;

        oebpsFolder.file(`chapter${index + 1}.xhtml`, chapterContent);
    }

    // Füge die geladenen Bilder zum ZIP hinzu
    for (const [filename, blob] of imageFiles) {
        imagesFolder.file(filename, blob);
    }

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

/**
 * Holt die vollständigen Node-Daten für eine Liste von IDs in einer einzigen,
 * effizienten API-Anfrage. Benötigt die aktive vault_id.
 * @param {string[]} ids - Eine Liste von Node-IDs.
 * @param {number} vaultId - Die ID des aktiven Vaults.
 * @returns {Promise<Array<Object>>} - Ein Promise, das ein Array von Node-Objekten liefert.
 */
const getFullNodesByIds = async (ids, vaultId) => {
    if (!ids || ids.length === 0) {
        return [];
    }
    if (!vaultId) {
        throw new Error("vaultId is required to fetch node details.");
    }

    try {
        const url = `/api/vaults/${vaultId}/nodes/bulk-get`;
        // Wir stellen weiterhin sicher, dass die IDs Strings sind, da UUIDs Strings sind.
        const stringIds = ids.map(String);
        const payload = {
            node_ids: stringIds
        };


        const response = await api.post(url, payload);
        // `versionsWithContent` wäre ein passenderer Name, aber wir behalten `nodesWithContent` für Konsistenz.
        const versionsWithContent = response.data;

        if (!versionsWithContent) {
            // ... (Fehlerbehandlung bleibt gleich)
            throw new Error("Could not fetch node details from server.");
        }

        // ======================= DER ENTSCHEIDENDE FIX =======================
        // Erstelle die Map, indem du die `node_id`-Eigenschaft aus dem Version-Objekt als Schlüssel nimmst.
        // Und um sicherzustellen, dass wir nicht versehentlich ein Version-Objekt in den Rest des Codes
        // weitergeben, erstellen wir ein neues Objekt, das wie ein "Node"-Objekt aussieht.
        const nodesById = new Map();
        for (const version of versionsWithContent) {
            // Der Schlüssel ist die ID des Nodes.
            const key = String(version.node_id);

            nodesById.set(key, version);
        }
        // ====================================================================

        const sortedNodes = stringIds.map(id => {
            const versionData = nodesById.get(id);
            if (!versionData) return null;

            // Transformiere das Version-Objekt in ein Node-ähnliches Objekt, das der EPUB-Generator erwartet.
            // Wir müssen den Titel aus den Version-Daten nehmen.
            // WENN der Titel NICHT im versionData-Objekt ist, wird `undefined` verwendet, was zu Fehlern führt.
            // Dies ist der kritischste Punkt, der im Backend sichergestellt werden muss.
            return {
                id: versionData.node_id,
                title: versionData.title || "Titel nicht gefunden", // Fallback, falls das Backend den Titel nicht liefert
                content: versionData.content,
                // ... füge weitere Eigenschaften hinzu, die `generateEpub` benötigen könnte
            };
        }).filter(Boolean);

        if (sortedNodes.length !== stringIds.length) {
            console.warn(`[Export Service] Mismatch in fetched nodes. Requested ${stringIds.length}, but received and matched ${sortedNodes.length}.`);
        }

        return sortedNodes;

    } catch (error) {
        // ... (Fehlerbehandlung bleibt gleich)
        console.error(`[Export Service] Failed to fetch full nodes:`, error);
        throw error;
    }
};
/**
 * Orchestriert den EPUB-Export für die ausgewählten Nodes.
 * Benötigt jetzt die `activeVault`-ID.
 */
export const exportSelectionAsEpub = async (treeData, selectedIds, activeVault) => {
  try {
    const orderedIds = getIdsInOrder(treeData, selectedIds);
    if (orderedIds.length === 0) return false;
    
    // Rufe die neue, effiziente Funktion mit der vault_id auf
    const nodes = await getFullNodesByIds(orderedIds, activeVault.id);
    
    const toc = generateTocForSelectedNodes(treeData, selectedIds);
    
    await generateEpub(nodes, toc);
    return true;
  } catch (error) {
    console.error("Failed to export EPUB:", error);
    return false;
  }
};

/**
 * Orchestriert den Markdown-Export für die ausgewählten Nodes.
 * Benötigt jetzt die `activeVault`-ID.
 */
export const exportSelectionAsMarkdown = async (treeData, selectedIds, activeVault) => {
    try {
        const orderedIds = getIdsInOrder(treeData, selectedIds);
        if (orderedIds.length === 0) return false;

        // Rufe die neue, effiziente Funktion mit der vault_id auf
        const nodes = await getFullNodesByIds(orderedIds, activeVault.id);

        const markdownContent = nodes.map(node => `# ${node.title}\n\n${node.content || ''}`).join('\n\n---\n\n');
        
        const blob = new Blob([markdownContent], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `knowledge-base-export-${new Date().toISOString().split('T')[0]}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        return true;
    } catch (error) {
        console.error("Failed to export Markdown:", error);
        return false;
    }
};