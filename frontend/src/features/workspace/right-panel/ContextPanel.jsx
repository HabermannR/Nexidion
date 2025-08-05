import React from 'react';
import { Tabs, Tab } from 'react-bootstrap';
import VersionHistoryTab from './VersionHistoryTab.jsx';
import ChatTab from './ChatTab.jsx';
import WorkflowTab from './WorkflowTab.jsx';
import ToolsTab from './ToolsTab.jsx';


// Importiere die CSS-Datei, die wir gleich befüllen werden.
import './ContextPanel.css';

export default function ContextPanel() {
    return (
        // 1. DIESER DIV ist jetzt der Flex-Container, der die Höhe kontrolliert.
        <div className="context-panel-container">
            <Tabs
                defaultActiveKey="versions"
                id="context-panel-tabs"
                mountOnEnter
                unmountOnExit
                // `fill` sorgt dafür, dass die Tabs die volle Breite einnehmen.
                // WICHTIG: Keine Flexbox-Klassen mehr hier!
                fill
            >
                <Tab eventKey="chat" title="Chat">
                    <ChatTab />
                </Tab>

                <Tab eventKey="versions" title="Versionen">
                    <VersionHistoryTab />
                </Tab>

                <Tab eventKey="tools" title="Tools">
                    <ToolsTab />
                </Tab>

                <Tab eventKey="workflows" title="Workflows">
                    <div className="p-3">
                        <WorkflowTab />
                    </div>
                </Tab>
            </Tabs>
        </div>
    );
}