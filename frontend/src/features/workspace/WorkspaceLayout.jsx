import React, { useRef, useEffect, useState, useCallback, useMemo  } from 'react'; // KORREKTUR: useState und useCallback wieder hinzugefügt
import { Outlet, useParams, Link } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import { useWorkspaceStore } from './workspaceStore';


import ProjectTree from '../project-tree/ProjectTree.jsx';
import ContextPanel from './ContextPanel.jsx';
import ContextBarContainer from './ContextBarContainer.jsx';
import './WorkspaceLayout.css';

// The BreadcrumbTrail component (KEINE ÄNDERUNG)
const BreadcrumbTrail = ({ path }) => {
    if (!path || path.length === 0) return null;
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

export default function WorkspaceLayout() {
    const { vaultId } = useParams();

    // --- ZUSTAND AUS DEM GLOBALEN STORE ---
    const resetWorkspaceContext = useWorkspaceStore((state) => state.resetWorkspaceContext);
    const breadcrumbPath = useWorkspaceStore((state) => state.breadcrumbPath);
    const activeContextTab = useWorkspaceStore((state) => state.activeContextTab);
    const setActiveContextTab = useWorkspaceStore((state) => state.setActiveContextTab);

    // --- LOKALER UI-ZUSTAND (nur für dieses Layout relevant) ---
    // KORREKTUR: Die fehlenden State-Variablen und Handler wurden wiederhergestellt
    const [rightPanelMode, setRightPanelMode] = useState('normal');
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const previousVaultIdRef = useRef(vaultId);
    const programmaticResizeRef = useRef(false);

    // Vault-Wechsel-Effekt
    useEffect(() => {
        if (vaultId !== previousVaultIdRef.current) {
            resetWorkspaceContext();
            previousVaultIdRef.current = vaultId;
        }
    }, [vaultId, resetWorkspaceContext]);

    // --- UI-HANDLER ---
    // KORREKTUR: Fehlende Handler wiederhergestellt
    const handleMobileNavClose = useCallback(() => setShowMobileTree(false), []);

    const treeComponent = useMemo(() => (
        <ProjectTree onNodeClick={handleMobileNavClose} />
    ), [handleMobileNavClose]);

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


    return (
        <>
            {/* --- Desktop Layout --- */}
            <div className="main-content-area d-none d-lg-flex">
                <PanelGroup direction="horizontal" onLayout={handleLayout}>

                    {/* Left Panel */}
                    <Panel ref={leftPanelRef} id="left-panel" defaultSize={20} minSize={15} order={1} className="pane-template" collapsible>
                        <div className="left-panel-content-wrapper">
                            <div className="p-2 border-bottom bg-light">
                                <h6 className="mb-0 small text-muted text-uppercase">Navigation</h6>
                            </div>
                            <div className="scroll-pane">{treeComponent}</div>
                            <ContextBarContainer />
                        </div>
                    </Panel>
                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>

                    {/* Center Panel */}
                    <Panel id="center-panel" minSize={30} order={2} className="pane-template">
                        <div className="desktop-action-bar p-2 d-flex align-items-center border-bottom bg-light">
                            <Button variant="outline-secondary" size="sm" onClick={toggleLeftPanel} title="Navigation umschalten">☰ Nav</Button>
                            <div className="vr mx-2"></div>
                            <div className="breadcrumb-wrapper mx-2 flex-grow-1">
                                <BreadcrumbTrail path={breadcrumbPath} />
                            </div>
                            <ButtonGroup size="sm">
                                {/* KORREKTUR: Fehlende onClick-Handler wiederhergestellt */}
                                <Button variant={rightPanelMode === 'expanded' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('expanded')} title="Context Breit">{'<'}</Button>
                                <Button variant={rightPanelMode === 'normal' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('normal')} title="Context Normal">{'|'}</Button>
                                <Button variant={rightPanelMode === 'collapsed' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('collapsed')} title="Context Aus">{'>'}</Button>
                            </ButtonGroup>
                        </div>
                        <div className="scroll-pane px-4 pb-4">
                            <Outlet />
                        </div>
                    </Panel>
                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>

                    {/* Right Panel */}
                    <Panel ref={rightPanelRef} id="right-panel" defaultSize={25} minSize={15} order={3} className="pane-template" collapsible>
                        <ContextPanel
                            activeKey={activeContextTab}
                            onTabSelect={setActiveContextTab}
                        />
                    </Panel>

                </PanelGroup>
            </div>

            {/* --- Mobile Layout --- */}
            <div className="d-lg-none mobile-layout-wrapper">
                <div className="mobile-action-bar p-2 border-bottom bg-light">
                    <div className="mobile-action-bar-buttons w-100">
                        {/* KORREKTUR: Fehlende onClick-Handler wiederhergestellt */}
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileTree(true)}>☰ Navigation</Button>
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileContext(true)}>⚙️ Context</Button>
                    </div>
                </div>

                <main className="mobile-main-content p-3 pt-0">
                    <Outlet />
                </main>

                <footer className="mobile-fixed-footer">
                    <ContextBarContainer />
                </footer>
            </div>

            <Offcanvas show={showMobileTree} onHide={() => setShowMobileTree(false)} placement="start" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton>
                    <Offcanvas.Title>Navigation</Offcanvas.Title>
                </Offcanvas.Header>
                <Offcanvas.Body className="d-flex flex-column p-0">
                    <div className="flex-grow-1 overflow-auto p-3">{treeComponent}</div>
                    <ContextBarContainer />
                </Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileContext} onHide={() => setShowMobileContext(false)} placement="end" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton className="p-2">
                    <Offcanvas.Title>Context</Offcanvas.Title>
                </Offcanvas.Header>
                <Offcanvas.Body className="d-flex flex-column p-0">
                    <ContextPanel
                        activeKey={activeContextTab}
                        onTabSelect={setActiveContextTab}
                    />
                    <ContextBarContainer/>
                </Offcanvas.Body>
            </Offcanvas>
        </>
    );
}