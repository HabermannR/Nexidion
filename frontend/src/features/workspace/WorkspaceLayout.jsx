import React, { useState, useRef, useMemo } from 'react';
import { Outlet, Link, useLoaderData } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import ProjectTree from './left-panel/ProjectTree.jsx';
import ContextPanel from './right-panel/ContextPanel.jsx';
import './WorkspaceLayout.css';

// Import the new "dumb" presentational component
import ContextBarDisplay from './ContextBarDisplay.jsx';

// Import Zustand hooks
import { useWorkspaceStore } from './workspaceStore.js';
import { shallow } from 'zustand/shallow';

// The BreadcrumbTrail component remains unchanged.
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
    // --- LOCAL UI-ZUSTAND (for panel control, etc.) ---
    const [rightPanelMode, setRightPanelMode] = useState('normal');
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const [breadcrumbPath, setBreadcrumbPath] = useState([]);
    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const programmaticResizeRef = useRef(false);

    // --- DATA LOGIC (from React Router loader) ---
    const treeData = useLoaderData();

    const outletContext = useMemo(() => ({
        setBreadcrumbPath,
        treeData
    }), [treeData]); // The dependency array is key!

    // --- ZUSTAND HOOK (acts as the "Container" logic) ---
    // This parent component subscribes to the store ONCE.
    // Comment out this entire block.
    /*
    const {
        selectionSize,
        savedSetsForDisplay,
        clearSelection,
        setSelection,
        saveCurrentSet,
        deleteSet
    } = useWorkspaceStore(
        (state) => ({
            selectionSize: state.selectedNodeIds.size,
            savedSetsForDisplay: Object.entries(state.savedSets).map(([name, ids]) => ({
                name,
                count: ids.length,
                ids
            })),
            clearSelection: state.clearSelection,
            setSelection: state.setSelection,
            saveCurrentSet: state.saveCurrentSet,
            deleteSet: state.deleteSet,
        }),
        shallow
    );
    */

    // --- UI-HANDLER ---
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

    // --- MEMOIZED COMPONENTS ---
    const treeComponent = useMemo(() => (
        <ProjectTree treeData={treeData || []} />
    ), [treeData]);

    // Create a single, shared instance of the "dumb" display component.
    // We pass the state and actions from our single Zustand subscription as props.
    // Comment out this block.
    /*
    const contextBarComponent = (
        <ContextBarDisplay
            selectionSize={selectionSize}
            savedSets={savedSetsForDisplay}
            onClear={clearSelection}
            onSave={saveCurrentSet}
            onLoadSet={setSelection}
            onDeleteSet={deleteSet}
        />
    );
    */

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
                            {/* Render the shared component instance here */}
                            {/* {contextBarComponent} */}

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
                            <Outlet context={outletContext} />
                        </div>
                    </Panel>

                    {/* Right Panel */}
                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>
                    <Panel ref={rightPanelRef} id="right-panel" defaultSize={25} minSize={15} order={3} className="pane-template" collapsible>
                        <ContextPanel />
                    </Panel>

                </PanelGroup>
            </div>

            {/* --- Mobile Layout --- */}
            <div className="d-lg-none d-flex flex-column h-100">
                <div className="mobile-action-bar p-2 border-bottom bg-light">
                    <div className="mobile-action-bar-buttons w-100">
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileTree(true)}>☰ Navigation</Button>
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileContext(true)}>⚙️ Context</Button>
                    </div>
                </div>
                <div className="mobile-content-scroll-area">
                    <Outlet context={outletContext} />
                </div>
                {/* Render the exact same shared component instance here */}
                {/* {contextBarComponent} */}

            </div>

            {/* --- Mobile Offcanvas Menus --- */}
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