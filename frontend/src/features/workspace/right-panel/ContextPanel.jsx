// src/features/workspace/right-panel/ContextPanel.jsx

import React from 'react';
import { Tabs, Tab } from 'react-bootstrap';

// Wir importieren die einzelnen Tab-Komponenten
import ChatTab from './ChatTab.jsx'; // Pfad ggf. anpassen
import WorkflowTab from './WorkflowTab.jsx'; // Pfad ggf. anpassen
import VersionHistoryTab from './VersionHistoryTab.jsx'; // Pfad ggf. anpassen
import { useWorkspaceStore } from '../workspaceStore.js'; // Für die selectedNodeIds

// Das ContextPanel ist jetzt eine sehr einfache Layout-Komponente.
// Es empfängt die Daten, die es an seine Kinder weitergeben muss.
export default function ContextPanel({ versions, activeNode }) {
    // Die selectedNodeIds für den WorkflowTab holen wir weiterhin aus dem Store,
    // da dies reiner UI-Zustand ist.
    const selectedNodeIds = useWorkspaceStore((state) => state.selectedNodeIds);

    return (
        <Tabs
            defaultActiveKey="chat"
            id="context-panel-tabs"
            className="px-2 pt-2"
            mountOnEnter // Optimierung: rendert den Tab-Inhalt erst, wenn er geklickt wird
            unmountOnExit // Optimierung: entfernt den Tab-Inhalt, wenn ein anderer geklickt wird (außer beim Chat)
            fill
        >
            <Tab eventKey="chat" title="Chat">
                {/* Der Chat-Tab braucht keine Props, er verwaltet seinen Zustand selbst */}
                <ChatTab />
            </Tab>
            <Tab eventKey="workflows" title="Workflows">
                <div className="scroll-pane" style={{ padding: '1rem' }}>
                    <WorkflowTab selectedNodeIds={selectedNodeIds} />
                </div>
            </Tab>
            <Tab eventKey="versions" title="Versionen">
                {/* Die VersionHistoryTab bekommt jetzt die Daten als Prop. Kein eigenes Laden mehr! */}
                <div className="scroll-pane">
                    <VersionHistoryTab versions={versions} />
                </div>
            </Tab>
        </Tabs>
    );
}