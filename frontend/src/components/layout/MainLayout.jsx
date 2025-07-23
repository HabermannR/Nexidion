import React, { useState, lazy, Suspense } from 'react';
import Offcanvas from 'react-bootstrap/Offcanvas';
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Button from 'react-bootstrap/Button';
import Spinner from 'react-bootstrap/Spinner';

// Import der CSS-Datei
import './MainLayout.css';

// Lazy-loaded Komponenten
const ProjectTree = lazy(() => import('../nodes/ProjectTree'));

const MainLayout = React.memo(function MainLayout({
                                                      treeData, activeNodeId, onNodeClick, onAddNode, onDeleteNode, onMoveNode,
                                                      mainContent, versionHistory, contextPanel, onLoadVersions, areVersionsLoaded
                                                  }) {
    // States und Handler bleiben unverändert
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const [showMobileVersions, setShowMobileVersions] = useState(false);
    const [isTreeVisible, setIsTreeVisible] = useState(true);
    const [contextLayoutMode, setContextLayoutMode] = useState('normal');
    const [showDesktopVersions, setShowDesktopVersions] = useState(false);

    const handleToggleContext = () => {
        setContextLayoutMode(currentMode => {
            if (currentMode === 'normal') return 'expanded';
            if (currentMode === 'expanded') return 'collapsed';
            return 'normal';
        });
    };

    const handleVersionsClick = (mode) => {
        // Schritt 1: Lade die Daten, wenn nötig
        if (!areVersionsLoaded && onLoadVersions) {
            onLoadVersions();
        }

        // Schritt 2: Öffne das entsprechende Offcanvas
        if (mode === 'mobile') {
            setShowMobileVersions(true);
        } else {
            setShowDesktopVersions(true);
        }
    };

    // Berechnung der Spaltenbreiten bleibt unverändert
    const treeBaseWidth = 3;
    const contextDisplayWidth = contextLayoutMode === 'expanded' ? 6 : 3;
    const treeSpaceUsed = isTreeVisible ? treeBaseWidth : 0;
    const contextSpaceUsed = contextLayoutMode === 'collapsed' ? 0 : contextDisplayWidth;
    const mainColSize = 12 - treeSpaceUsed - contextSpaceUsed;

    // Komponenten-Instanzen vorbereiten
    const treeComponent = (
        <Suspense fallback={<div className="p-3 text-center small"><Spinner animation="border" size="sm" /> Lade Baum...</div>}>
            <ProjectTree
                treeData={treeData} activeNodeId={activeNodeId}
                onNodeClick={(node) => { onNodeClick(node); setShowMobileTree(false); }}
                onAddNode={onAddNode} onDeleteNode={onDeleteNode} onMoveNode={onMoveNode}
            />
        </Suspense>
    );

    return (
        <Container fluid className="main-layout-container g-0">
            {/* MOBILE ACTION BAR: Wird nur auf Mobile angezeigt und ist jetzt korrekt im Layoutfluss */}
            <div className="d-lg-none mobile-action-bar bg-light border-bottom p-2">
                <Row className="g-2 align-items-center">
                    <Col><Button variant="outline-secondary" className="w-100" onClick={() => setShowMobileTree(true)}>☰ Nav</Button></Col>
                    <Col><Button variant="outline-secondary" className="w-100" onClick={() => handleVersionsClick('mobile')}>🕒 Ver</Button></Col>
                    <Col><Button variant="outline-secondary" className="w-100" onClick={() => setShowMobileContext(true)}>⚙️ Context</Button></Col>
                </Row>
            </div>

            <Row className="main-layout-row g-0">
                {/* 1. DESKTOP TREE VIEW (linke Spalte) */}
                {isTreeVisible && (
                    <Col lg={treeBaseWidth} className="d-none d-lg-flex tree-column">
                        <div className="tree-wrapper">{treeComponent}</div>
                    </Col>
                )}

                {/* 2. MAIN CONTENT (mittlere Spalte - jetzt auch auf Mobile die scrollbare Spalte) */}
                <Col xs={12} lg={mainColSize} className="main-content-col">
                    <div className="desktop-action-bar d-none d-lg-flex p-2 align-items-center bg-light">
                        <Button variant="outline-secondary" size="sm" onClick={() => setIsTreeVisible(p => !p)}>{isTreeVisible ? '☰ Nav Aus' : '☰ Nav Ein'}</Button>
                        <div className="vr mx-2"></div>
                        <Button variant="outline-secondary" size="sm" onClick={() => handleVersionsClick('desktop')}>🕒 Versionen</Button>
                        <span className="flex-grow-1"></span>
                        <Button variant="outline-secondary" size="sm" onClick={handleToggleContext}>{contextLayoutMode === 'collapsed' && 'Context Ein »'}{contextLayoutMode === 'normal' && 'Context Breit »'}{contextLayoutMode === 'expanded' && '« Context Aus'}</Button>
                    </div>
                    <div className="main-content-wrapper">{mainContent}</div>
                </Col>

                {/* 3. DESKTOP CONTEXT SIDEBAR (rechte Spalte) */}
                {contextLayoutMode !== 'collapsed' && (
                    <Col lg={contextDisplayWidth} className="d-none d-lg-block context-panel-col">
                        <div className="desktop-sidebar-wrapper">{contextPanel}</div>
                    </Col>
                )}
            </Row>

            {/* OFF-CANVAS CONTAINER (mit neuen CSS-Klassen für gezieltes Styling) */}
            <Offcanvas show={showMobileTree} onHide={() => setShowMobileTree(false)} placement="start" className="offcanvas-tree">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{treeComponent}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileContext} onHide={() => setShowMobileContext(false)} placement="end" className="offcanvas-context">
                <Offcanvas.Header closeButton><Offcanvas.Title>Context & Chat</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{contextPanel}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileVersions} onHide={() => setShowMobileVersions(false)} placement="bottom" style={{ height: '75vh' }} className="offcanvas-versions-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Version History</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{versionHistory}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showDesktopVersions} onHide={() => setShowDesktopVersions(false)} placement="end" className="offcanvas-versions-desktop">
                <Offcanvas.Header closeButton><Offcanvas.Title>Version History</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{versionHistory}</Offcanvas.Body>
            </Offcanvas>
        </Container>
    );
});
export default MainLayout;