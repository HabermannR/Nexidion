// src/features/workspace/WorkspaceLayout.jsx

import React, { useState, useRef, useMemo } from 'react';
// WICHTIG: Wir importieren Outlet, Link und useLoaderData.
// useRouteLoaderData ist hier nicht mehr nötig, da der Loader direkt an dieser Route hängt.
import { Outlet, Link, useLoaderData } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import ProjectTree from './left-panel/ProjectTree.jsx';
import ContextBar from './left-panel/ContextBar.jsx';
import ContextPanel from './right-panel/ContextPanel.jsx';
import './WorkspaceLayout.css';

// Die BreadcrumbTrail-Komponente kann unverändert bleiben.
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
    // --- LOKALER UI-ZUSTAND (für die Panel-Steuerung, etc.) ---
    const [rightPanelMode, setRightPanelMode] = useState('normal');
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const [breadcrumbPath, setBreadcrumbPath] = useState([]); // Wird vom Kind (NodeContent) befüllt
    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const programmaticResizeRef = useRef(false);

    // --- DATEN-LOGIK (SAUBER & EINFACH) ---
    // Der Baum kommt direkt vom Loader dieser Route (`vaultTreeLoader`).
    // React Router sorgt dafür, dass diese Daten aktuell sind.
    const treeData = useLoaderData();

    // --- UI-HANDLER (unverändert) ---
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

    // --- MEMOISIERTE KOMPONENTEN ---

    // Der Baum wird nur neu erstellt, wenn sich die `treeData` wirklich ändern (bei Vault-Wechsel).
    // Diese Optimierung ist korrekt und sinnvoll.
    const treeComponent = useMemo(() => (
        <ProjectTree treeData={treeData || []} />
    ), [treeData]);

    // Das `ContextPanel` im rechten Bereich wird einfach so gerendert. Es ist
    // nicht mehr von Daten aus diesem Layout abhängig, sondern holt sich seinen
    // Zustand (wie die `diffSelection`) direkt aus dem `zustand`-Store.

    console.log('🍞 WorkspaceLayout: aktueller breadcrumbPath:', breadcrumbPath);

    return (
        <>
            {/* --- Desktop Layout --- */}
            <div className="main-content-area d-none d-lg-flex">
                <PanelGroup direction="horizontal" onLayout={handleLayout}>

                    {/* Left Panel */}
                    <Panel ref={leftPanelRef} id="left-panel" defaultSize={20} minSize={15} order={1} className="pane-template" collapsible>
                        <div className="left-panel-content-wrapper">
                            <div className="scroll-pane">{treeComponent}</div>
                            <ContextBar />
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
                                <Button variant={rightPanelMode === 'expanded' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('expanded')} title="Context Breit">{'<'}</Button>
                                <Button variant={rightPanelMode === 'normal' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('normal')} title="Context Normal">{'|'}</Button>
                                <Button variant={rightPanelMode === 'collapsed' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('collapsed')} title="Context Aus">{'>'}</Button>
                            </ButtonGroup>
                        </div>
                        <div className="scroll-pane px-4 pb-4">
                            {/*
                                Das Outlet rendert das Kind, also <NodeContent />.
                                Wir übergeben die `setBreadcrumbPath`-Funktion via context,
                                damit der Kind-Inhalt den Breadcrumb im Eltern-Layout setzen kann.
                                Dies ist ein Standard-Pattern in React Router.
                            */}
                            <Outlet context={{ setBreadcrumbPath, treeData }} />
                        </div>
                    </Panel>

                    {/* Right Panel */}
                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>
                    <Panel ref={rightPanelRef} id="right-panel" defaultSize={25} minSize={15} order={3} className="pane-template" collapsible>
                        {/* Das ContextPanel ist jetzt völlig unabhängig. */}
                        <ContextPanel />
                    </Panel>

                </PanelGroup>
            </div>

            {/* --- Mobile Layout (unverändert in der Logik) --- */}
            <div className="d-lg-none d-flex flex-column h-100">
                <div className="mobile-action-bar p-2 border-bottom bg-light">
                    <div className="mobile-action-bar-buttons w-100">
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileTree(true)}>☰ Navigation</Button>
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileContext(true)}>⚙️ Context</Button>
                    </div>
                </div>
                <div className="mobile-content-scroll-area">
                    <Outlet context={{ setBreadcrumbPath, treeData }} />
                </div>
                <ContextBar />
            </div>

            {/* --- Mobile Offcanvas Menus (unverändert in der Logik) --- */}
            <Offcanvas show={showMobileTree} onHide={() => setShowMobileTree(false)} placement="start" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body>{treeComponent}</Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileContext} onHide={() => setShowMobileContext(false)} placement="end" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Context</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body className="p-0">
                    <ContextPanel />
                </Offcanvas.Body>
            </Offcanvas>
        </>
    );
}