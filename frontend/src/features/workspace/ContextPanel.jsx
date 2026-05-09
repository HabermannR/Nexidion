// src/features/workspace/ContextPanel.jsx

import React from 'react';
import { Tabs, Tab } from 'react-bootstrap';
import VersionHistoryTab from '../version-history/VersionHistoryTab.jsx';
import AgentTab from '../agent/AgentTab.jsx';
import ToolsTab from '../tools/ToolsTab.jsx';

import './ContextPanel.css';

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
                <Tab eventKey="agent" title="Agent"><AgentTab /></Tab>
                <Tab eventKey="versions" title="Versionen"><VersionHistoryTab /></Tab>
                <Tab eventKey="tools" title="Tools">
                    <div className="tab-pane-content-wrapper">
                        <ToolsTab />
                    </div>
                </Tab>
            </Tabs>
        </div>
    );
}
