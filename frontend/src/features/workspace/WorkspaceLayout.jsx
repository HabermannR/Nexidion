import React, { useMemo, useState, useRef, useCallback, useEffect, useLayoutEffect } from 'react';
import { Outlet, useParams, Link } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient';
import { useWorkspaceStore } from './workspaceStore';
import { WorkspaceDataProvider } from './WorkspaceDataContext';

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

    // --- LOKALER UI-ZUSTAND ---
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
            setIsReadyForQueries(false);
            resetWorkspaceContext();
            setBreadcrumbPath([]);
        }
        previousVaultIdRef.current = currentVaultId;
    }, [vaultId, resetWorkspaceContext]);

    useEffect(() => {
        if (!isReadyForQueries) {
            const timer = setTimeout(() => {
                setIsReadyForQueries(true);
            }, 0);
            return () => clearTimeout(timer);
        }
    }, [isReadyForQueries]);

    // --- DATA LOGIC (SERVER-STATE) ---
    // Holt die Baumdaten für den aktuellen Vault.
    // TanStack Query managed Caching, Lade- & Fehlerzustände.
    const { data: treeData, isLoading: isTreeLoading } = useQuery({
        queryKey: ['vaultTree', vaultId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes?format=tree`).then(res => res.data),
        enabled: !!vaultId && isReadyForQueries,
    });

    // --- ABGELEITETE DATEN & CONTEXT-WERTE ---
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

    // Context-Wert für das React Router <Outlet>, falls direkte Kinder ihn brauchen.
    const outletContext = useMemo(() => ({
        setBreadcrumbPath,
        treeData,
        isReadyForQueries,
    }), [treeData, isReadyForQueries]);

    // Context-Wert für unseren WorkspaceDataProvider.
    // Stellt die Baumdaten allen verschachtelten Komponenten zur Verfügung.
    const workspaceDataContextValue = useMemo(() => ({
        treeData: treeData ?? [], // Stellt sicher, dass immer ein Array übergeben wird
        isTreeLoading,
    }), [treeData, isTreeLoading]);

    // --- UI-HANDLER ---
    const handleMobileNavClose = useCallback(() => setShowMobileTree(false), []);
    const treeComponent = useMemo(() => (
        <ProjectTree
            treeData={treeData}
            isLoading={isTreeLoading}
            onNodeClick={handleMobileNavClose}
            isReadyForQueries={isReadyForQueries}
        />
    ), [treeData, isTreeLoading, handleMobileNavClose, isReadyForQueries]);

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
        <WorkspaceDataProvider value={workspaceDataContextValue}>
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
                        {/* `treeData` wird NICHT mehr durchgereicht, um Prop-Drilling zu vermeiden */}
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

                <main className="mobile-main-content p-3 pt-0">
                    <Outlet context={outletContext} />
                </main>

                <footer className="mobile-fixed-footer">
                    <ContextBarContainer selectedNodes={selectedNodesWithData} />
                </footer>
            </div>

            <Offcanvas show={showMobileTree} onHide={() => setShowMobileTree(false)} placement="start" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton><Offcanvas.Title>Navigation</Offcanvas.Title></Offcanvas.Header>
                <Offcanvas.Body className="d-flex flex-column p-0">
                    <div className="flex-grow-1 overflow-auto p-3">{treeComponent}</div>
                    <ContextBarContainer selectedNodes={selectedNodesWithData} />
                </Offcanvas.Body>
            </Offcanvas>

            <Offcanvas show={showMobileContext} onHide={() => setShowMobileContext(false)} placement="end" className="offcanvas-full-mobile">
                <Offcanvas.Header closeButton className="p-2">
                    <Offcanvas.Title>Context</Offcanvas.Title>
                </Offcanvas.Header>
                <Offcanvas.Body className="d-flex flex-column p-0">
                    <ContextPanel
                        selectedNodes={selectedNodesWithData}
                        activeKey={activeContextTab}
                        onTabSelect={setActiveContextTab}
                    />
                    <ContextBarContainer selectedNodes={selectedNodesWithData} />
                </Offcanvas.Body>
            </Offcanvas>
        </WorkspaceDataProvider>
    );
}