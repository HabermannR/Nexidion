// src/components/layout/MainLayout.jsx 

import React, { useState, lazy, Suspense } from 'react'; 
import Offcanvas from 'react-bootstrap/Offcanvas';
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Button from 'react-bootstrap/Button';
import './MainLayout.css';

// Die permanenten Komponenten werden jetzt hier importiert
const ContextPanel = lazy(() => import('../context/ContextPanel'));
import ProjectTree from '../nodes/ProjectTree';

const MainLayout = React.memo(function MainLayout({ // "function" Keyword hier ist guter Stil
    // Props für den Baum
    treeData,
    activeNodeId,
    onNodeClick,
    onAddNode,
    onDeleteNode,
    onMoveNode,
    // Props für den Hauptinhalt
    mainContent,
    // Props für die Versionen
    versionHistory,
    // Callback-Funktionen
    onNodeUpdate,
    // Props für mobile Versionen-Ansicht
    onSelectVersionForMobile,
    onCompareVersionForMobile,
    onShowCurrentForMobile,
    diffSelection
}) {
	
    const [showTreePanel, setShowTreePanel] = useState(false);
    const [showContextPanel, setShowContextPanel] = useState(false);
    const [showVersionsPanel, setShowVersionsPanel] = useState(false);

    // ====================================================================
    // WIR ERSTELLEN DIE KOMPONENTEN-INSTANZEN HIER EINMAL
    // ====================================================================

    const treeComponent = (
        <ProjectTree
            treeData={treeData}
            activeNodeId={activeNodeId}
            onNodeClick={(node) => {
                onNodeClick(node);
                setShowTreePanel(false); // Panel nach Klick schließen
            }}
            onAddNode={onAddNode}
            onDeleteNode={onDeleteNode}
            onMoveNode={onMoveNode}
        />
    );

    // Die EINE, PERMANENTE ContextPanel-Instanz
    const contextPanelComponent = (
        <Suspense fallback={<div className="p-3 text-center small">Lade Kontext...</div>}>
            <ContextPanel onNodeUpdate={onNodeUpdate} />
        </Suspense>
    );

    // Die VersionHistory Komponente auch, falls sie im Offcanvas gebraucht wird
    // Wir nehmen die Props von NodesView entgegen
    const versionHistoryComponent = React.cloneElement(versionHistory, {
        onSelectVersion: (v) => {
            onSelectVersionForMobile(v);
        },
        onCompareVersion: (v) => {
            onCompareVersionForMobile(v);
            setShowVersionsPanel(false);
        },
        onShowCurrent: () => {
            onShowCurrentForMobile();
            setShowVersionsPanel(false);
        }
    });

    return (
        <Container fluid className="main-layout-container">
            <Row className="main-layout-row g-0">
                {/* 1. Desktop Tree View */}
                <Col lg={3} className="d-none d-lg-flex tree-column p-0">
                    {treeComponent}
                </Col>

                {/* 2. Main Content */}
                <Col xs={12} lg={6} className="main-content-col order-2 order-lg-2">
                    {mainContent}
                </Col>

                {/* 3. Mobile Action Bar */}
                <Col xs={12} className="order-1 d-lg-none">
                    <Row className="g-2 p-3 align-items-center bg-light border-bottom">
                        <Col><Button variant="outline-secondary" className="w-100" onClick={() => setShowTreePanel(true)}>☰ Nav</Button></Col>
                        <Col><Button variant="outline-secondary" className="w-100" onClick={() => setShowVersionsPanel(true)}>🕒 Ver</Button></Col>
                        <Col><Button variant="outline-secondary" className="w-100" onClick={() => setShowContextPanel(true)}>⚙️ Context</Button></Col>
                    </Row>
                </Col>

                {/* 4. Desktop Context/Version Sidebar */}
                <Col lg={3} className="d-none d-lg-block order-lg-3 context-panel-col">
                    <div className="desktop-sidebar-wrapper">
                        {contextPanelComponent}
                        <hr className="my-3" />
                        {versionHistory}
                    </div>
                </Col>
            </Row>

            {/* 5. Die Offcanvas-Container, die die EINMAL erstellten Komponenten rendern */}

            <Offcanvas show={showTreePanel} onHide={() => setShowTreePanel(false)} placement="start">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{treeComponent}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showContextPanel} onHide={() => setShowContextPanel(false)} placement="end">
                <Offcanvas.Header closeButton><Offcanvas.Title>Context & Chat</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{contextPanelComponent}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showVersionsPanel} onHide={() => setShowVersionsPanel(false)} placement="bottom" style={{ height: '75vh' }}>
                <Offcanvas.Header closeButton><Offcanvas.Title>Version History</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{versionHistoryComponent}</Offcanvas.Body>
            </Offcanvas>
        </Container>
    );
});
export default MainLayout;