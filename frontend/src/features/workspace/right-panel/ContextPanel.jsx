import React from 'react';
import { Tabs, Tab } from 'react-bootstrap';
import VersionHistoryTab from './VersionHistoryTab.jsx';
import Chat from './Chat/Chat.jsx'; // Pfad ggf. anpassen
import WorkflowTab from './WorkflowTab.jsx';
import ToolsTab from './ToolsTab.jsx';

import './ContextPanel.css';

export default function ContextPanel({ selectedNodes, activeKey, onTabSelect }) {

    return (
        <div className="context-panel-container">
            <Tabs
                activeKey={activeKey}
                onSelect={onTabSelect}
                id="context-panel-tabs"
                fill
                className="context-panel-grid-tabs"
            >
                {/*
                  TABS MIT EIGENEM FLEX-LAYOUT:
                  Diese Komponenten werden DIREKT platziert, da ihr Wurzel-Element
                  bereits die Eigenschaft `flex: 1` besitzt und somit das direkte Kind
                  des `.tab-pane`-Flex-Containers sein kann.
                */}
                <Tab eventKey="chat" title="Chat">
                    <Chat />
                </Tab>

                <Tab eventKey="versions" title="Versionen">
                    <VersionHistoryTab />
                </Tab>


                {/*
                  TABS MIT EINFACHEM INHALT:
                  Diese Komponenten haben kein eigenes Layout und benötigen den Wrapper,
                  der für sie die Rolle des wachsenden Flex-Kindes übernimmt.
                */}
                <Tab eventKey="tools" title="Tools">
                    <div className="tab-pane-content-wrapper">
                        <ToolsTab selectedNodes={selectedNodes} />
                    </div>
                </Tab>

                <Tab eventKey="workflows" title="Workflows">
                    <div className="tab-pane-content-wrapper">
                        {/* WICHTIG: Die Komponente selbst hat jetzt keinen .p-3 Wrapper mehr nötig */}
                        <WorkflowTab selectedNodes={selectedNodes} />
                    </div>
                </Tab>
            </Tabs>
        </div>
    );
}