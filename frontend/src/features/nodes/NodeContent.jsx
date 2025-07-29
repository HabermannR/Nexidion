// src/features/nodes/NodeContent.jsx

import React from 'react';
import { useLoaderData, useParams } from 'react-router-dom';

export default function NodeContent() {
    // Mit dem useParams-Hook können wir auf die Parameter aus der URL zugreifen
    const { vaultId, nodeId } = useParams();

    // Mit useLoaderData können wir auf die Daten zugreifen, die vom
    // vaultTreeLoader (oder einem zukünftigen nodeContentLoader) geladen wurden.
    const loaderData = useLoaderData();

    return (
        <div>
            <h2>Node-Inhalt</h2>
            <hr />
            <p>Dies ist die Inhaltsansicht für den ausgewählten Knoten.</p>

            <div className="mt-4 p-3 bg-light rounded">
                <h5 className="text-muted">Debugging-Infos:</h5>
                <ul>
                    <li><strong>Vault ID aus URL:</strong> {vaultId}</li>
                    <li><strong>Node ID aus URL:</strong> {nodeId}</li>
                </ul>
                <details>
                    <summary>Vom Loader geladene Daten anzeigen</summary>
                    <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {JSON.stringify(loaderData, null, 2)}
          </pre>
                </details>
            </div>
        </div>
    );
}