// src/features/workspace/WorkspaceLayout.jsx

import React, { useMemo, useState, useRef, useCallback, useEffect, useLayoutEffect  } from 'react';
import { Outlet, useParams, Link } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';
import { useWorkspaceStore } from './workspaceStore';

import ProjectTree from './left-panel/ProjectTree.jsx';
import ContextPanel from './right-panel/ContextPanel.jsx';
import ContextBarContainer from './ContextBarContainer.jsx';
import './WorkspaceLayout.css';

// The BreadcrumbTrail component
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

// Helper function to flatten the tree
const flattenTree = (nodes) => {
    const flatList = [];
    const recurse = (nodesToFlatten) => {
        for (const node of nodesToFlatten) {
            const { children, ...rest } = node;
            flatList.push(rest);
            if (children && children.length > 0) {
                recurse(children);
            }
        }
    };
    recurse(nodes);
    return flatList;
};

export default function WorkspaceLayout() {
    const { vaultId } = useParams();
    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const resetWorkspaceContext = useWorkspaceStore((state) => state.resetWorkspaceContext);
    // --- LOCAL UI-ZUSTAND (for panel control, etc.) ---
    const [rightPanelMode, setRightPanelMode] = useState('normal');
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const [breadcrumbPath, setBreadcrumbPath] = useState([]);
    const [activeContextTab, setActiveContextTab] = useState('chat');
    const [isReadyForQueries, setIsReadyForQueries] = useState(true);
    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const previousVaultIdRef = useRef(vaultId);
    const programmaticResizeRef = useRef(false);

    useLayoutEffect(() => {
        const currentVaultId = vaultId;
        const previousVaultId = previousVaultIdRef.current;

        if (currentVaultId && previousVaultId && currentVaultId !== previousVaultId) {
            // Diese Aktionen passieren jetzt garantiert synchron, bevor es weitergeht.
            setIsReadyForQueries(false);
            resetWorkspaceContext();
            setBreadcrumbPath([]);
        }

        // Diese Ref-Aktualisierung ist jetzt auch synchron und sicher.
        previousVaultIdRef.current = currentVaultId;

    }, [vaultId, resetWorkspaceContext]);

    useEffect(() => {
        // Wenn die Anfragen deaktiviert wurden...
        if (!isReadyForQueries) {
            // ...aktiviere sie im nächsten Render-Zyklus wieder.
            // Ein setTimeout von 0 schiebt diese Aktion ans Ende der Event-Loop,
            // sodass der Zustand-Reset von Zustand garantiert vorher verarbeitet wurde.
            const timer = setTimeout(() => {
                setIsReadyForQueries(true);
            }, 0);
            return () => clearTimeout(timer);
        }
    }, [isReadyForQueries]);

    // --- DATA LOGIC  ---
    const { data: treeData, isLoading: isTreeLoading } = useQuery({
        queryKey: ['vaultTree', vaultId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes?format=tree&v3=true`).then(res => res.data),
        // +++ START DER KORREKTUR +++
        // 4. Die `enabled`-Option verwenden, um die Anfrage zu steuern.
        enabled: !!vaultId && isReadyForQueries,
        // +++ ENDE DER KORREKTUR +++
    });

    // --- Memoized Derived Data  ---
    const allNodesFlat = useMemo(() => {
        if (!treeData) return [];
        return flattenTree(treeData);
    }, [treeData]);

    const selectedNodesWithData = useMemo(() => {
        if (!allNodesFlat || allNodesFlat.length === 0 || selectedNodeIds.size === 0) {
            return [];
        }
        const nodeMap = new Map(allNodesFlat.map(node => [node.id, node]));
        return Array.from(selectedNodeIds)
            .map(id => {
                const node = nodeMap.get(id);
                return { id, title: node?.title || 'Unknown Node' };
            })
            .sort((a, b) => a.title.localeCompare(b.title));
    }, [selectedNodeIds, allNodesFlat]);


    const outletContext = useMemo(() => ({
        setBreadcrumbPath,
        treeData,
        // +++ START DER KORREKTUR +++
        // 5. Den Bereitschafts-Status an alle Kind-Routen weitergeben.
        isReadyForQueries,
        // +++ ENDE DER KORREKTUR +++
    }), [treeData, isReadyForQueries]); // Abhängigkeit hinzufügen

    const handleMobileNavClose = useCallback(() => {
        setShowMobileTree(false);
    }, []);

    const treeComponent = useMemo(() => (
        // Pass data and loading state as props to the ProjectTree
        <ProjectTree
            treeData={treeData}
            isLoading={isTreeLoading}
            onNodeClick={handleMobileNavClose}
            isReadyForQueries={isReadyForQueries}
        />
    ), [treeData, isTreeLoading, handleMobileNavClose]);

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


    return (
        <>
            {/* --- Desktop Layout --- */}
            <div className="main-content-area d-none d-lg-flex">
                <PanelGroup direction="horizontal" onLayout={handleLayout}>

                    {/* Left Panel */}
                    <Panel ref={leftPanelRef} id="left-panel" defaultSize={20} minSize={15} order={1} className="pane-template" collapsible>
                        <div className="left-panel-content-wrapper">
                            <div className="scroll-pane">{treeComponent}</div>
                            <ContextBarContainer selectedNodes={selectedNodesWithData} />
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
                    <PanelResizeHandle className="resize-handle-outer"><div className="resize-handle-inner" /></PanelResizeHandle>
                    {/* Right Panel */}
                    <Panel ref={rightPanelRef} id="right-panel" defaultSize={25} minSize={15} order={3} className="pane-template" collapsible>
                        {/* 3. Pass the state and handler down as props */}
                        <ContextPanel
                            selectedNodes={selectedNodesWithData}
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
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileTree(true)}>☰ Navigation</Button>
                        <Button variant="outline-secondary" className="flex-fill" onClick={() => setShowMobileContext(true)}>⚙️ Context</Button>
                    </div>
                </div>

                {/* This is the new scrollable content area */}
                <main className="mobile-main-content p-3 pt-0">
                    <Outlet context={outletContext} />
                </main>

                {/* The context bar is now wrapped in our fixed footer element */}
                <footer className="mobile-fixed-footer">
                    <ContextBarContainer selectedNodes={selectedNodesWithData} />
                </footer>
            </div>

            <Offcanvas show={showMobileTree} onHide={() => setShowMobileTree(false)} placement="start" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                {/*
                  Make the body a flex container so we can position the context bar at the bottom.
                  p-0 removes default padding so the context bar is flush with the edges.
                */}
                <Offcanvas.Body className="d-flex flex-column p-0">
                    {/* The tree now needs to be in its own scrollable sub-container */}
                    <div className="flex-grow-1 overflow-auto p-3">
                        {treeComponent}
                    </div>
                    {/* Add a second, independent instance of the context bar here */}
                    <ContextBarContainer selectedNodes={selectedNodesWithData} />
                </Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileContext} onHide={() => setShowMobileContext(false)} placement="end" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton className="p-2">
                    <Offcanvas.Title>Context</Offcanvas.Title>
                </Offcanvas.Header>
                {/*
                  Apply the same flex-column pattern here as we did for the left panel.
                */}
                <Offcanvas.Body className="d-flex flex-column p-0">
                    {/* The existing ContextPanel now becomes the scrollable main content. */}
                    {/* It already handles its own internal padding and scrolling, so we just let it grow. */}
                    <ContextPanel
                        selectedNodes={selectedNodesWithData}
                        activeKey={activeContextTab}
                        onTabSelect={setActiveContextTab}
                    />
                    <ContextBarContainer selectedNodes={selectedNodesWithData} />
                </Offcanvas.Body>
            </Offcanvas>
        </>
    );
}