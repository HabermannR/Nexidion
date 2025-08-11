// src/features/workspace/right-panel/ContextPanel.jsx (V4-Version)

import React from 'react';
import { Tabs, Tab } from 'react-bootstrap';
import VersionHistoryTab from '../version-history/VersionHistoryTab.jsx';
import Chat from '../chat/Chat.jsx';
import WorkflowTab from '../workflows/WorkflowTab.jsx';
import ToolsTab from '../tools/ToolsTab.jsx'; // Dieser Import bleibt

import './ContextPanel.css';

// +++ ÄNDERUNG: Die 'selectedNodes'-Prop wird nicht mehr empfangen. +++
export default function ContextPanel({ activeKey, onTabSelect }) {

    return (
        <div className="context-panel-container">
            <Tabs
                activeKey={activeKey}
                onSelect={onTabSelect}
                id="context-panel-tabs"
                fill
                className="context-panel-grid-tabs"
            >
                 <Tab eventKey="chat" title="Chat"><Chat /></Tab>
                <Tab eventKey="versions" title="Versionen"><VersionHistoryTab /></Tab>

                <Tab eventKey="tools" title="Tools">
                    <div className="tab-pane-content-wrapper">
                         <ToolsTab />
                    </div>
                </Tab>

                <Tab eventKey="workflows" title="Workflows">
                    <div className="tab-pane-content-wrapper">
                         <WorkflowTab />
                    </div>
                </Tab>
            </Tabs>
        </div>
    );
}