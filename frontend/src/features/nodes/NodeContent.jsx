import React, { useState, useEffect } from 'react'; // <-- HIER IST DIE KORREKTUR
import { useLoaderData, useOutletContext, Form } from 'react-router-dom';
import { Button } from 'react-bootstrap';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Annahme: Deine wiederverwendbaren UI-Komponenten liegen in einem Unterordner.
import ContentHeader from './ui/ContentHeader';
import NodeEditor from './ui/NodeEditor';


// ===================================================================
// HILFSFUNKTION: Sucht rekursiv den Pfad zum Ziel-Node im Baum.
// ===================================================================
const findPathInTree = (nodes, nodeId, currentPath = []) => {
    for (const node of nodes) {
        // Erstelle den Pfad für den aktuellen Knoten
        const newPath = [...currentPath, {
            id: node.id,
            title: node.title,
            to: `/vaults/${node.vault_id}/nodes/${node.id}`
        }];

        // Wenn wir den gesuchten Knoten gefunden haben, geben wir den Pfad zurück
        if (node.id === nodeId) {
            return newPath;
        }

        // Wenn der Knoten Kinder hat, suchen wir rekursiv weiter
        if (node.children && node.children.length > 0) {
            const foundPath = findPathInTree(node.children, nodeId, newPath);
            if (foundPath) {
                return foundPath;
            }
        }
    }
    // Wenn nichts in diesem Zweig gefunden wurde, geben wir null zurück
    return null;
};


/**
 * NodeContent ist die Hauptkomponente zur Anzeige und Bearbeitung des Inhalts eines Nodes.
 * Sie berechnet den Breadcrumb-Pfad und sendet ihn an das Eltern-Layout.
 */
export default function NodeContent() {
    // 1. DATEN VOM LOADER (der aktuelle Node)
    const node = useLoaderData();

    // 2. DATEN AUS DEM KONTEXT (vom WorkspaceLayout)
    const { setBreadcrumbPath, treeData } = useOutletContext();

    // 3. LOKALER UI-STATE
    const [isEditing, setIsEditing] = useState(false);
    const [editableContent, setEditableContent] = useState('');

    // 4. EFFEKTE ZUR SYNCHRONISATION
    useEffect(() => {
        // Dieser Effekt aktualisiert den Breadcrumb im Eltern-Layout.
        if (node && treeData && typeof setBreadcrumbPath === 'function') {

            const path = findPathInTree(treeData, node.id);

            if (path) {
                setBreadcrumbPath(path);
            }
        }

        // Cleanup-Funktion: Leert den Breadcrumb, wenn diese Komponente verschwindet.
        return () => {
            if (typeof setBreadcrumbPath === 'function') {
                setBreadcrumbPath([]);
            }
        };
    }, [node, treeData, setBreadcrumbPath]);

    useEffect(() => {
        // Dieser Effekt aktualisiert den Editor-Inhalt.
        if (node) {
            setEditableContent(node.content);
            setIsEditing(false);
        }
    }, [node]);

    // Handler zum Abbrechen der Bearbeitung
    const handleCancelEdit = () => {
        setIsEditing(false);
        setEditableContent(node.content);
    };

    // Fallback-UI
    if (!node) {
        return <div className="p-4 text-muted">Node wird geladen...</div>;
    }

    // 5. RENDER-LOGIK
    return (
        <div>
            {/* Das Breadcrumb-Rendering findet jetzt im WorkspaceLayout statt. */}

            <ContentHeader
                title={node.title}
                isEditing={isEditing}
                onEditClick={() => setIsEditing(true)}
            />

            <hr />

            {isEditing ? (
                <Form method="patch" onSubmit={() => setIsEditing(false)}>
                    <NodeEditor
                        content={editableContent}
                        onContentChange={setEditableContent}
                    />
                    <input type="hidden" name="content" value={editableContent} />
                    <input type="hidden" name="title" value={node.title} />
                    <input type="hidden" name="intent" value="updateContent" />
                    <div className="d-flex gap-2 mt-2">
                        <Button type="submit" variant="primary">Speichern</Button>
                        <Button type="button" variant="outline-secondary" onClick={handleCancelEdit}>
                            Abbrechen
                        </Button>
                    </div>
                </Form>
            ) : (
                <div className="markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {node.content || ''}
                    </ReactMarkdown>
                </div>
            )}
        </div>
    );
}