import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { Outlet, useParams, Link } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import { useWorkspaceStore } from './workspaceStore';
import apiClient from '../../api/apiClient.js';

import ProjectTree from '../project-tree/ProjectTree.jsx';
import ContextPanel from './ContextPanel.jsx';
import ContextBarContainer from './ContextBarContainer.jsx';
import './WorkspaceLayout.css';

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

    // --- LOKALER UI-ZUSTAND ---
    const[rightPanelMode, setRightPanelMode] = useState('normal');
    const[showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const previousVaultIdRef = useRef(vaultId);
    const programmaticResizeRef = useRef(false);

    // --- SUCHE STATE ---
    const [searchInput, setSearchInput] = useState('');
    const[debouncedSearch, setDebouncedSearch] = useState('');

    // Debounce Such-Eingabe
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(searchInput), 300);
        return () => clearTimeout(timer);
    }, [searchInput]);

    // Suche über TanStack Query ausführen
    const { data: searchData, isFetching, isSuccess } = useQuery({
        queryKey:['nodeSearch', vaultId, debouncedSearch],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/full-search?q=${encodeURIComponent(debouncedSearch)}`).then(res => res.data),
        enabled: !!vaultId && debouncedSearch.trim().length > 0,
    });

    // Berechne die gehighlighteten IDs
    const highlightedNodeIds = useMemo(() => {
        if (debouncedSearch.trim().length === 0 || !searchData?.results) {
            return new Set();
        }
        return new Set(searchData.results.map(r => r.id));
    }, [searchData, debouncedSearch]);

    // --- BERECHNUNG DER FARB-LOGIK & ZÄHLER FÜR DIE SUCHE ---
    const isSearchActive = searchInput.trim().length > 0;
    const isSearchLoading = isSearchActive && (searchInput !== debouncedSearch || isFetching);
    const isSearchFinished = isSearchActive && !isSearchLoading && isSuccess;
    
    // Zähler aus dem API-Resultat extrahieren (falls fertig)
    const searchResultsCount = isSearchFinished && searchData ? searchData.count : null;

    const searchInputStyle = {
        backgroundColor: isSearchLoading ? '#e9ecef' : (isSearchFinished ? '#d1e7dd' : '#ffffff'),
        transition: 'background-color 0.3s ease-in-out'
    };

    // Vault-Wechsel-Effekt
    useEffect(() => {
        if (vaultId !== previousVaultIdRef.current) {
            resetWorkspaceContext();
            setSearchInput(''); // Suche zurücksetzen beim Vault-Wechsel
            previousVaultIdRef.current = vaultId;
        }
    }, [vaultId, resetWorkspaceContext]);

    // --- UI-HANDLER ---
    const handleMobileNavClose = useCallback(() => setShowMobileTree(false),[]);

    // Tree Component wird memoized inkl. highlightedNodeIds
    const treeComponent = useMemo(() => (
        <ProjectTree 
            onNodeClick={handleMobileNavClose} 
            highlightedNodeIds={highlightedNodeIds} 
        />
    ), [handleMobileNavClose, highlightedNodeIds]);

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
                                <h6 className="mb-0 small text-muted text-uppercase">
                                    Navigation {searchResultsCount !== null && <span style={{ textTransform: 'none' }} className="fw-bold text-success">({searchResultsCount})</span>}
                                </h6>
                                <div className="mt-2">
                                    <input
                                        type="search"
                                        className="form-control form-control-sm"
                                        placeholder="Suche in Nodes..."
                                        value={searchInput}
                                        onChange={(e) => setSearchInput(e.target.value)}
                                        style={searchInputStyle}
                                    />
                                </div>
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
                    <Offcanvas.Title>
                        Navigation {searchResultsCount !== null && <span style={{ fontSize: '1rem' }} className="text-success">({searchResultsCount})</span>}
                    </Offcanvas.Title>
                </Offcanvas.Header>
                <div className="p-2 border-bottom bg-light">
                    <input
                        type="search"
                        className="form-control form-control-sm"
                        placeholder="Suche in Nodes..."
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        style={searchInputStyle}
                    />
                </div>
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