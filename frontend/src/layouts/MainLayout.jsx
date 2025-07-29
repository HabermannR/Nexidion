// src/layouts/MainLayout.jsx

import React, { useState, useRef } from 'react';
import { Outlet, useNavigation } from 'react-router-dom';

// Lokale Imports
import ProjectTree from '../features/nodes/ProjectTree.jsx';
import './MainLayout.css';

// Bibliothek-Imports
import 'bootstrap/dist/css/bootstrap.min.css';
import { Navbar, Container, Nav, Button, ButtonGroup, Offcanvas } from 'react-bootstrap';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

// Platzhalter für zukünftige Komponenten
const ContextPanel = () => <div className="p-3 text-muted">Context Panel</div>;


export default function MainLayout() {
    // ===================================================================
    // 1. HOOKS (IMMER AM ANFANG UND UNBEDINGT)
    // ===================================================================
    const navigation = useNavigation();
    const [rightPanelMode, setRightPanelMode] = useState('normal');
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const programmaticResizeRef = useRef(false);

    // ===================================================================
    // 2. LOGIK, DIE HOOKS VERWENDET
    // ===================================================================
    // Wir ermitteln den Ladezustand, um der UI subtile Hinweise zu geben.
    const isLoading = navigation.state === 'loading';

    // Handler-Funktionen für das Layout
    const handleLayout = () => {
        if (programmaticResizeRef.current) {
            programmaticResizeRef.current = false;
            return;
        }
        setRightPanelMode('custom');
    };

    const setRightPanelState = (mode) => {
        programmaticResizeRef.current = true;
        const rightPanel = rightPanelRef.current;
        if (!rightPanel) return;

        if (mode === "collapsed") {
            if (!rightPanel.isCollapsed()) rightPanel.collapse();
        } else {
            if (rightPanel.isCollapsed()) rightPanel.expand();
            const targetSize = mode === "expanded" ? 40 : 25;
            rightPanel.resize(targetSize);
        }
        setRightPanelMode(mode);
    };

    const toggleLeftPanel = () => {
        const leftPanel = leftPanelRef.current;
        if (leftPanel) {
            leftPanel.isCollapsed() ? leftPanel.resize(25) : leftPanel.collapse();
        }
    };

    // ===================================================================
    // 3. HAUPT-RENDER-LOGIK
    // ===================================================================
    return (
        // Wir fügen eine CSS-Klasse hinzu, wenn die App lädt.
        // Das ist nützlich für Effekte wie das Dimmen der UI.
        <div className={`app-container ${isLoading ? 'is-loading' : ''}`}>
            <Navbar bg="light" variant="light" className="app-header border-bottom">
                <Container fluid>
                    <Navbar.Brand><strong>Nexidion v3</strong></Navbar.Brand>
                    <Nav className="ms-auto">
                        <Button variant="outline-secondary" size="sm">Log Out</Button>
                    </Nav>
                </Container>
            </Navbar>

            {/* Mobile Bar */}
            <div className="d-lg-none mobile-action-bar p-2">
                <ButtonGroup className="w-100">
                    <Button variant="secondary" onClick={() => setShowMobileTree(true)}>☰ Baum</Button>
                    <Button variant="secondary" onClick={() => setShowMobileContext(true)}>Context</Button>
                </ButtonGroup>
            </div>

            {/* Desktop Layout */}
            <div className="main-content-area d-none d-lg-flex">
                <PanelGroup direction="horizontal" onLayout={handleLayout}>
                    <Panel ref={leftPanelRef} defaultSize={25} minSize={5} collapsible order={1}>
                        <div className="pane-template left-pane">
                            <div className="scroll-pane p-2">
                                <ProjectTree />
                            </div>
                        </div>
                    </Panel>

                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>

                    <Panel minSize={30} order={2}>
                        <div className="pane-template center-pane">
                            <div className="desktop-action-bar p-2 d-flex align-items-center">
                                <Button variant="outline-secondary" size="sm" onClick={toggleLeftPanel} title="Navigation umschalten"><i className='bx bx-menu'></i></Button>
                                <div className="vr mx-2"></div>
                                <span className="fw-bold small text-muted">Ansicht</span>
                                <span className="flex-grow-1"></span>
                                <ButtonGroup size="sm">
                                    <Button variant={rightPanelMode === 'expanded' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('expanded')} title="Rechte Spalte ausklappen"><i className='bx bx-chevrons-left'></i></Button>
                                    <Button variant={rightPanelMode === 'normal' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('normal')} title="Normale Breite"><i className='bx bx-columns'></i></Button>
                                    <Button variant={rightPanelMode === 'collapsed' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('collapsed')} title="Rechte Spalte einklappen"><i className='bx bx-chevrons-right'></i></Button>
                                </ButtonGroup>
                            </div>
                            <div className="scroll-pane p-4">
                                <Outlet />
                            </div>
                        </div>
                    </Panel>

                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>

                    <Panel ref={rightPanelRef} defaultSize={25} minSize={15} collapsible order={3}>
                        <div className="pane-template right-pane">
                            <ContextPanel />
                        </div>
                    </Panel>
                </PanelGroup>
            </div>

            {/* Mobile Content Area */}
            <div className="d-lg-none flex-grow-1" style={{ minHeight: 0 }}>
                <div className="scroll-pane p-3">
                    <Outlet />
                </div>
            </div>

            {/* Offcanvas für Mobile */}
            <Offcanvas show={showMobileTree} onHide={() => setShowMobileTree(false)} placement="start">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body><ProjectTree /></Offcanvas.Body>
            </Offcanvas>
            <Offcanvas show={showMobileContext} onHide={() => setShowMobileContext(false)} placement="end">
                <Offcanvas.Header closeButton><Offcanvas.Title>Context</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body><ContextPanel /></Offcanvas.Body>
            </Offcanvas>
        </div>
    );
}