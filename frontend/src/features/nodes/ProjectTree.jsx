// src/features/nodes/ProjectTree.jsx

import React, { Suspense } from 'react';
import { useLoaderData, Await } from 'react-router-dom';
import { Spinner } from 'react-bootstrap';

// Eine eigene Fallback-Komponente, die ihren eigenen Render loggt.
const LoadingFallback = () => {
    console.log("[Fallback] Suspense-Fallback wird gerendert! Zeige Spinner an.");
    return <Spinner animation="border" size="sm" />;
};

// Die Komponente, die die Daten anzeigt, loggt ebenfalls ihren Render.
const Tree = ({ treeData }) => {
    console.log("[Tree] Daten sind da! Rendere den Baum.");
    return (
        <div>
            <h6 className="text-muted mb-2">Projektbaum</h6>
            <pre style={{ fontSize: '10px', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                {JSON.stringify(treeData, null, 2)}
            </pre>
        </div>
    );
};

export default function ProjectTree() {
    const treeDataPromise = useLoaderData();
    // Logge, dass die Hauptkomponente mit dem Promise gerendert wird.
    console.log("[ProjectTree] Hauptkomponente wird gerendert. Promise ist bereit.");

    return (
        <Suspense fallback={<LoadingFallback />}>
            <Await
                resolve={treeDataPromise}
                errorElement={<p className="text-danger small">Fehler beim Laden des Baums.</p>}
            >
                {(resolvedTreeData) => {
                    // Logge, dass Await die Daten aufgelöst hat.
                    console.log("[Await] Promise wurde aufgelöst. Übergebe Daten an die Tree-Komponente.");
                    return <Tree treeData={resolvedTreeData} />;
                }}
            </Await>
        </Suspense>
    );
}