import React, { useState, useRef } from 'react';
import { Outlet, Link, useLoaderData } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import ProjectTree from '../features/nodes/ProjectTree.jsx';
import './WorkspaceLayout.css';

// Die Breadcrumb-Komponente lebt direkt hier im Layout.
const BreadcrumbTrail = ({ path }) => {
    if (!path || path.length === 0) {
        return null;
    }
    return (
        <Breadcrumb listProps={{ className: "mb-0 bg-transparent p-0 small" }}>
            {path.map((crumb, index) => (
                <Breadcrumb.Item
                    key={crumb.id}
                    linkAs={Link}
                    linkProps={{ to: crumb.to }}
                    active={index === path.length - 1}
                >
                    {crumb.title}
                </Breadcrumb.Item>
            ))}
        </Breadcrumb>
    );
};

// Platzhalter für die zukünftigen Komponenten.
const ContextPanel = () => (
    <div className="p-3 text-muted">Context Panel</div>
);

const VersionHistoryPanel = () => (
    <div className="p-3 text-muted">Version History Panel</div>
);


/**
 * WorkspaceLayout ist das Haupt-Layout für den "laufenden Betrieb".
 */
export default function WorkspaceLayout() {
    // State für die Panel- und Mobil-Steuerung
    const [rightPanelMode, setRightPanelMode] = useState('normal');
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const [showMobileVersions, setShowMobileVersions] = useState(false);
    const [breadcrumbPath, setBreadcrumbPath] = useState([]);

    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const programmaticResizeRef = useRef(false);
    const treeData = useLoaderData();

    // Handler-Funktionen für die UI-Steuerung
    const handleLayout = () => {
        if (programmaticResizeRef.current) {
            programmaticResizeRef.current = false;
            return;
        }
        setRightPanelMode('custom');
    };

    const setRightPanelState = (mode) => {
        programmaticResizeRef.current = true;
        const panel = rightPanelRef.current;
        if (!panel) return;

        if (mode === "collapsed") {
            if (!panel.isCollapsed()) panel.collapse();
        } else {
            if (panel.isCollapsed()) panel.expand();
            const targetSize = mode === "expanded" ? 40 : 25;
            panel.resize(targetSize);
        }
        setRightPanelMode(mode);
    };

    const toggleLeftPanel = () => {
        const panel = leftPanelRef.current;
        if (panel) {
            panel.isCollapsed() ? panel.resize(20) : panel.collapse();
        }
    };

    const handleVersionsClick = (mode) => {
        if (mode === 'mobile') {
            setShowMobileVersions(true);
        } else {
            // TODO: Logik für Desktop-Versionen implementieren (z.B. ein weiteres Offcanvas)
            alert('Desktop-Versionen anzeigen (noch nicht implementiert)');
        }
    };

    // Komponenten-Instanzen vorbereiten
    const treeComponent = <ProjectTree />;
    const contextComponent = <ContextPanel />;
    const versionHistoryComponent = <VersionHistoryPanel />;

    return (
        <>
            {/* --- Desktop Layout --- */}
            <div className="main-content-area d-none d-lg-flex">
                <PanelGroup direction="horizontal" onLayout={handleLayout}>

                    {/* Left Panel */}
                    <Panel ref={leftPanelRef} id="left-panel" defaultSize={20} minSize={15} order={1} className="pane-template" collapsible>
                        <div className="scroll-pane">{treeComponent}</div>
                    </Panel>
                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>

                    {/* Center Panel */}
                    <Panel id="center-panel" minSize={30} order={2} className="pane-template">
                        <div className="desktop-action-bar p-2 d-flex align-items-center border-bottom bg-light">
                            <Button variant="outline-secondary" size="sm" onClick={toggleLeftPanel} title="Navigation umschalten">☰ Nav</Button>
                            <div className="vr mx-2"></div>
                            <Button variant="outline-secondary" size="sm" onClick={() => handleVersionsClick('desktop')}>🕒 Versionen</Button>

                            <div className="breadcrumb-wrapper mx-2">
                                <BreadcrumbTrail path={breadcrumbPath} />
                            </div>

                            <ButtonGroup size="sm">
                                <Button variant={rightPanelMode === 'expanded' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('expanded')} title="Context Breit">Breit</Button>
                                <Button variant={rightPanelMode === 'normal' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('normal')} title="Context Normal">Normal</Button>
                                <Button variant={rightPanelMode === 'collapsed' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('collapsed')} title="Context Aus">Aus</Button>
                            </ButtonGroup>
                        </div>
                        <div className="scroll-pane pt-2 px-4 pb-4">
                            <Outlet context={{ setBreadcrumbPath, treeData  }} />
                        </div>
                    </Panel>

                    {/* Right Panel */}
                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>
                    <Panel ref={rightPanelRef} id="right-panel" defaultSize={25} minSize={15} order={3} className="pane-template" collapsible>
                        <div className="scroll-pane">{contextComponent}</div>
                    </Panel>

                </PanelGroup>
            </div>

            {/* --- Mobile Layout --- */}
            <div className="d-lg-none d-flex flex-column h-100">
                <div className="mobile-action-bar p-2 border-bottom bg-light">
                    <div className="mobile-action-bar-buttons w-100">
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileTree(true)}>☰ Nav</Button>
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => handleVersionsClick('mobile')}>🕒 Ver</Button>
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileContext(true)}>⚙️ Context</Button>
                    </div>
                </div>
                <div className="scroll-pane pt-2 px-3 pb-3 flex-grow-1">
                    <Outlet context={{ setBreadcrumbPath }} />
                </div>
            </div>

            {/* --- Mobile Offcanvas Menus --- */}
            <Offcanvas show={showMobileTree} onHide={() => setShowMobileTree(false)} placement="start" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{treeComponent}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileVersions} onHide={() => setShowMobileVersions(false)} placement="bottom" style={{ height: '75vh' }} className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Version History</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{versionHistoryComponent}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileContext} onHide={() => setShowMobileContext(false)} placement="end" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Context</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{contextComponent}</Offcanvas.Body>
            </Offcanvas>
        </>
    );
}