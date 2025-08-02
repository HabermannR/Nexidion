import React, {useState, useEffect} from "react";
// NEUE IMPORTS: useSubmit und useParams für Aktionen, useFetcher existierte schon im Plan
import {
    useLoaderData,
    useOutletContext,
    useSubmit,
    useParams,
    Form,
} from "react-router-dom";
// NEUER IMPORT: ButtonGroup & Dropdown werden indirekt über ContentHeader genutzt, aber es schadet nicht sie zu erwähnen
import {Button} from "react-bootstrap";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Die UI-Komponenten werden importiert
import ContentHeader from "./ui/ContentHeader"; // <-- Diese Komponente muss auch aktualisiert sein!
import NodeEditor from "./ui/NodeEditor";

// ===================================================================
// HILFSFUNKTION: Sucht rekursiv den Pfad zum Ziel-Node im Baum.
// (Diese Funktion bleibt unverändert)
// ===================================================================
const findPathInTree = (nodes, nodeId, currentPath = []) => {
    for (const node of nodes) {
        const newPath = [
            ...currentPath,
            {
                id: node.id,
                title: node.title,
                to: `/vaults/${node.vault_id}/nodes/${node.id}`,
            },
        ];

        if (node.id === nodeId) {
            return newPath;
        }

        if (node.children && node.children.length > 0) {
            const foundPath = findPathInTree(node.children, nodeId, newPath);
            if (foundPath) {
                return foundPath;
            }
        }
    }
    return null;
};

/**
 * NodeContent ist die Hauptkomponente zur Anzeige und Bearbeitung des Inhalts eines Nodes.
 * Sie steuert nun auch die Aktionen zum Umbenennen und Löschen.
 */
export default function NodeContent() {
    // 1. DATEN VOM LOADER
    const node = useLoaderData();

    // 2. DATEN AUS DEM KONTEXT
    const {setBreadcrumbPath, treeData} = useOutletContext();

    // 3. NEUE HOOKS FÜR AKTIONEN
    // useSubmit löst Aktionen (PATCH, DELETE etc.) aus, ohne eine <Form> zu benötigen.
    const submit = useSubmit();
    // useParams holt dynamische Teile der URL (z.B. die nodeId)
    const {vaultId, nodeId} = useParams();

    // 4. LOKALER UI-STATE
    const [isEditing, setIsEditing] = useState(false);
    const [editableContent, setEditableContent] = useState("");

    // 5. EFFEKTE ZUR SYNCHRONISATION (unverändert)
    useEffect(() => {
        if (node && treeData && typeof setBreadcrumbPath === "function") {
            const path = findPathInTree(treeData, node.id);
            if (path) {
                setBreadcrumbPath(path);
            }
        }
        return () => {
            if (typeof setBreadcrumbPath === "function") {
                setBreadcrumbPath([]);
            }
        };
    }, [node, treeData, setBreadcrumbPath]);

    useEffect(() => {
        if (node) {
            setEditableContent(node.content);
            // Wichtig: Beim Wechseln des Nodes den Edit-Modus immer beenden.
            setIsEditing(false);
        }
    }, [node]);

    // 6. NEUE HANDLER FÜR DIE NODE-AKTIONEN
    const handleRename = () => {
        const currentTitle = node.title;
        const newTitle = prompt("Neuen Titel für den Node eingeben:", currentTitle);

        if (newTitle && newTitle.trim() !== "" && newTitle !== currentTitle) {
            submit(
                {title: newTitle, intent: "renameNode"},
                {
                    method: "patch",
                    // encType: "application/json", // <-- DIESE ZEILE ENTFERNEN
                    action: `/vaults/${vaultId}/nodes/${nodeId}`,
                },
            );
        }
    };

    const handleDelete = () => {
        if (
            window.confirm(
                `Soll der Node "${node.title}" wirklich endgültig gelöscht werden? Diese Aktion kann nicht rückgängig gemacht werden.`,
            )
        ) {
            // Löst die `action` für den DELETE-Endpunkt aus.
            submit(
                {intent: "deleteNode"},
                {
                    method: "delete",
                    action: `/vaults/${vaultId}/nodes/${nodeId}`,
                },
            );
        }
    };

    // Handler zum Abbrechen der Bearbeitung (unverändert)
    const handleCancelEdit = () => {
        setIsEditing(false);
        setEditableContent(node.content);
    };

    // Fallback-UI
    if (!node) {
        return <div className="p-4 text-muted">Node wird geladen...</div>;
    }

    // 7. RENDER-LOGIK MIT AKTUALISIERTEM HEADER
    return (
        <div>
            {/*
                Die ContentHeader-Komponente erhält die neuen Handler als Props.
                Sie muss intern das ButtonGroup/Dropdown-Konstrukt implementiert haben.
            */}
            <ContentHeader
                currentNode={node}
                vaultId={vaultId}
                isEditing={isEditing}
                onEditClick={() => setIsEditing(true)}
                onRenameClick={handleRename}
                onDeleteClick={handleDelete}
            />

            {isEditing ? (
                // Das Formular zum Speichern des Inhalts bleibt unverändert.
                <Form method="patch" onSubmit={() => setIsEditing(false)}>
                    <NodeEditor
                        content={editableContent}
                        onContentChange={setEditableContent}
                    />
                    <input type="hidden" name="content" value={editableContent}/>
                    {/* Der Titel wird hier nicht mehr mitgesendet, um Konflikte zu vermeiden. */}
                    {/* Stattdessen wird ein klares 'intent' mitgeschickt. */}
                    <input type="hidden" name="intent" value="updateContent"/>
                    <div className="d-flex gap-2 mt-2">
                        <Button type="submit" variant="primary">
                            Speichern
                        </Button>
                        <Button
                            type="button"
                            variant="outline-secondary"
                            onClick={handleCancelEdit}
                        >
                            Abbrechen
                        </Button>
                    </div>
                </Form>
            ) : (
                <div className="markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {node.content || ""}
                    </ReactMarkdown>
                </div>
            )}
        </div>
    );
}
