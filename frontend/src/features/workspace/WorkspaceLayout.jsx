// src/features/workspace/WorkspaceLayout.jsx
import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { Outlet, useParams, Link } from 'react-router-dom';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { Button, ButtonGroup, Offcanvas, Breadcrumb } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import { useWorkspaceStore } from './workspaceStore';
import apiClient from '../../api/apiClient.js';

import ProjectTree from '../project-tree/ProjectTree.jsx';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery.js';
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

    // --- STATE FROM THE GLOBAL STORE ---
    const resetWorkspaceContext = useWorkspaceStore((state) => state.resetWorkspaceContext);
    const expandAll = useWorkspaceStore((state) => state.expandAll);
    const collapseAll = useWorkspaceStore((state) => state.collapseAll);
    const breadcrumbPath = useWorkspaceStore((state) => state.breadcrumbPath);
    const activeContextTab = useWorkspaceStore((state) => state.activeContextTab);
    const setActiveContextTab = useWorkspaceStore((state) => state.setActiveContextTab);

    // --- LOCAL UI STATE ---
    const [rightPanelMode, setRightPanelMode] = useState('normal');
    const [showMobileTree, setShowMobileTree] = useState(false);
    const [showMobileContext, setShowMobileContext] = useState(false);
    const leftPanelRef = useRef(null);
    const rightPanelRef = useRef(null);
    const previousVaultIdRef = useRef(vaultId);
    const programmaticResizeRef = useRef(false);

    // --- SEARCH STATE ---
    const [searchInput, setSearchInput] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [searchResultIndex, setSearchResultIndex] = useState(0);

    // Debounce search input
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(searchInput), 300);
        return () => clearTimeout(timer);
    }, [searchInput]);

    // Reset search index when the search term changes
    useEffect(() => {
        setSearchResultIndex(0);
    }, [debouncedSearch]);

    // Execute search via TanStack Query
    const { data: searchData, isFetching, isSuccess } = useQuery({
        queryKey: ['nodeSearch', vaultId, debouncedSearch],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/nodes/full-search?q=${encodeURIComponent(debouncedSearch)}`).then(res => res.data),
        enabled: !!vaultId && debouncedSearch.trim().length > 0,
    });

    const { data: vaultTreeDataForCollapse } = useVaultTreeQuery(vaultId);

    const searchResultIds = useMemo(() => {
        if (!searchData?.results) return [];

        // 1. Create a Set of all matched IDs from the backend
        const matchedIdsSet = new Set(searchData.results.map(r => r.id));

        // 2. We will store the visually ordered IDs here
        const orderedIds = [];

        // 3. Recursive function to traverse the tree top-to-bottom (Depth-First Search)
        const traverseTree = (nodes) => {
            if (!nodes) return;
            for (const node of nodes) {
                // If this node is a search result, add it to our ordered list
                if (matchedIdsSet.has(node.id)) {
                    orderedIds.push(node.id);
                    // Remove from Set to track leftovers
                    matchedIdsSet.delete(node.id);
                }
                // Continue down the children
                if (node.children && node.children.length > 0) {
                    traverseTree(node.children);
                }
            }
        };

        // 4. Run the traversal if we have tree data
        if (vaultTreeDataForCollapse?.tree) {
            traverseTree(vaultTreeDataForCollapse.tree);
        }

        // 5. Append any remaining search results that weren't found in the tree
        // (Serves as a fallback in case the tree data is out of sync or loading)
        for (const leftoverId of matchedIdsSet) {
            orderedIds.push(leftoverId);
        }

        return orderedIds;
    }, [searchData, vaultTreeDataForCollapse]);

    // Calculate the highlighted IDs
    const highlightedNodeIds = useMemo(() => {
        if (debouncedSearch.trim().length === 0 || !searchData?.results) {
            return new Set();
        }
        return new Set(searchData.results.map(r => r.id));
    }, [searchData, debouncedSearch]);

    // --- CALCULATION OF COLOR LOGIC & COUNTER FOR SEARCH ---
    const isSearchActive = searchInput.trim().length > 0;
    const isSearchLoading = isSearchActive && (searchInput !== debouncedSearch || isFetching);
    const isSearchFinished = isSearchActive && !isSearchLoading && isSuccess;

    // Extract counter from the API result (if finished)
    const searchResultsCount = isSearchFinished && searchData ? searchData.count : null;

    const searchInputStyle = {
        backgroundColor: isSearchLoading ? '#e9ecef' : (isSearchFinished ? '#d1e7dd' : '#ffffff'),
        transition: 'background-color 0.3s ease-in-out'
    };

    // Vault change effect
    useEffect(() => {
        if (vaultId !== previousVaultIdRef.current) {
            resetWorkspaceContext();
            setSearchInput(''); // Reset search on vault change
            previousVaultIdRef.current = vaultId;
        }
    }, [vaultId, resetWorkspaceContext]);

    // Jump UP (↑) means going backwards in the array (towards index 0)
    const handleJumpUp = () => {
        if (searchResultIds.length > 0) {
            setSearchResultIndex((prev) => (prev - 1 + searchResultIds.length) % searchResultIds.length);
        }
    };

    // Jump DOWN (↓) means going forwards in the array (towards the end)
    const handleJumpDown = () => {
        if (searchResultIds.length > 0) {
            setSearchResultIndex((prev) => (prev + 1) % searchResultIds.length);
        }
    };

    const scrollToNodeId = searchResultIds.length > 0 ? searchResultIds[searchResultIndex] : null;

    // --- UI HANDLERS ---
    const handleMobileNavClose = useCallback(() => setShowMobileTree(false), []);

    // Collect all non-leaf nodes for 'collapseAll'
    const allNonLeafIds = useMemo(() => {
        const ids = [];
        const collect = (nodes) => nodes?.forEach(n => {
            if (n.children?.length) { ids.push(n.id); collect(n.children); }
        });
        collect(vaultTreeDataForCollapse?.tree);
        return ids;
    }, [vaultTreeDataForCollapse]);

    const handleCollapseAll = useCallback(() => collapseAll(allNonLeafIds), [collapseAll, allNonLeafIds]);

    // Tree Component is memoized incl. highlightedNodeIds + scrollToNodeId
    const treeComponent = useMemo(() => (
        <ProjectTree
            onNodeClick={handleMobileNavClose}
            highlightedNodeIds={highlightedNodeIds}
            scrollToNodeId={scrollToNodeId}
        />
    ), [handleMobileNavClose, highlightedNodeIds, scrollToNodeId]);

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
                                <div className="d-flex align-items-center justify-content-between mb-2">
                                    <h6 className="mb-0 small text-muted text-uppercase flex-grow-1">
                                        Navigation
                                        {searchResultsCount !== null && (
                                            <span style={{ textTransform: 'none' }} className="fw-bold text-success ms-1">
                                                ({searchResultIndex + 1}/{searchResultsCount})
                                            </span>
                                        )}
                                    </h6>
                                    <ButtonGroup size="sm">
                                        <Button variant="outline-secondary" onClick={expandAll} title="Expand all"
                                            style={{ fontSize: '0.7rem', padding: '1px 5px' }}>↕ All</Button>
                                        <Button variant="outline-secondary" onClick={handleCollapseAll} title="Collapse all"
                                            style={{ fontSize: '0.7rem', padding: '1px 5px' }}>⊟ All</Button>
                                    </ButtonGroup>
                                </div>
                                <div className="d-flex gap-1">
                                    <input
                                        type="search"
                                        className="form-control form-control-sm flex-grow-1"
                                        placeholder="Search in nodes..."
                                        value={searchInput}
                                        onChange={(e) => setSearchInput(e.target.value)}
                                        style={searchInputStyle}
                                    />
                                    {searchResultIds.length > 1 && (
                                        <ButtonGroup size="sm" className="flex-shrink-0">
                                            <Button variant="outline-secondary" onClick={handleJumpUp} title="Previous result">↑</Button>
                                            <Button variant="outline-secondary" onClick={handleJumpDown} title="Next result">↓</Button>
                                        </ButtonGroup>
                                    )}
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
                            <Button variant="outline-secondary" size="sm" onClick={toggleLeftPanel} title="Toggle navigation">☰ Nav</Button>
                            <div className="vr mx-2"></div>
                            <div className="breadcrumb-wrapper mx-2 flex-grow-1">
                                <BreadcrumbTrail path={breadcrumbPath} />
                            </div>
                            <ButtonGroup size="sm">
                                <Button variant={rightPanelMode === 'expanded' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('expanded')} title="Context Wide">{'<'}</Button>
                                <Button variant={rightPanelMode === 'normal' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('normal')} title="Context Normal">{'|'}</Button>
                                <Button variant={rightPanelMode === 'collapsed' ? 'primary' : 'outline-secondary'} onClick={() => setRightPanelState('collapsed')} title="Context Off">{'>'}</Button>
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
                        Navigation {searchResultsCount !== null && <span style={{ fontSize: '1rem' }} className="text-success">({searchResultIndex + 1}/{searchResultsCount})</span>}
                    </Offcanvas.Title>
                </Offcanvas.Header>
                <div className="p-2 border-bottom bg-light">
                    <div className="d-flex gap-1">
                        <input
                            type="search"
                            className="form-control form-control-sm flex-grow-1"
                            placeholder="Search in nodes..."
                            value={searchInput}
                            onChange={(e) => setSearchInput(e.target.value)}
                            style={searchInputStyle}
                        />
                        {searchResultIds.length > 1 && (
                            <ButtonGroup size="sm" className="flex-shrink-0">
                                <Button variant="outline-secondary" onClick={handleJumpUp} title="Previous result">↑</Button>
                                <Button variant="outline-secondary" onClick={handleJumpDown} title="Next result">↓</Button>
                            </ButtonGroup>
                        )}
                    </div>
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