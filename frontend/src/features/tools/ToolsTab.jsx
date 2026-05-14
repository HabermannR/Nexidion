// src/features/workspace/ToolsTab.jsx

import React, { useState, useCallback, useMemo } from 'react';
import { Button, Alert, Form } from 'react-bootstrap';
import { useParams } from 'react-router-dom';

import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { copyContextContent } from '../../lib/clipboardService.js';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';

// Import our helper functions
import { getIdsInOrder, generateTocForSelectedNodes } from '../nodes/node.utils.js';
import { getFullNodesByIds } from '../../lib/exportService.js';

// Import the Agent styles so our chips look exactly the same!
import '../agent/AgentTab.css';

export default function ToolsTab() {
    const { vaultId } = useParams();

    const [copyContentStatus, setCopyContentStatus] = useState('idle'); // idle | copying | success | error
    const [copyContentError, setCopyContentError] = useState(null);

    const [copyTreeStatus, setCopyTreeStatus] = useState('idle');
    const [copyTreeError, setCopyTreeError] = useState(null);

    const [printStatus, setPrintStatus] = useState('idle'); // idle | preparing | preparing_all | error
    const [printError, setPrintError] = useState(null);

    // Toggles for Copy Tree
    const [includeUuid, setIncludeUuid] = useState(true);
    const [includeSummary, setIncludeSummary] = useState(false);

    const { data } = useVaultTreeQuery(vaultId);
    const treeData = data?.tree || [];
    const allNodesFlat = data?.allNodesFlat || [];

    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const openPrintPreview = useWorkspaceStore(state => state.openPrintPreview);

    const hasSelection = selectedNodeIds.size > 0;
    const hasNodes = allNodesFlat.length > 0;

    // Map IDs to titles and sort them exactly like the Agent Tab does
    const selectedNodes = useMemo(() => {
        if (allNodesFlat.length === 0 || selectedNodeIds.size === 0) return [];
        const nodeMap = new Map(allNodesFlat.map(n => [n.id, n]));
        return Array.from(selectedNodeIds)
            .map(id => ({ id, title: nodeMap.get(id)?.title || id }))
            .sort((a, b) => a.title.localeCompare(b.title));
    }, [selectedNodeIds, allNodesFlat]);

    const handleCopyContent = useCallback(async () => {
        setCopyContentStatus('copying');
        setCopyContentError(null);

        const getContextContentForApi = async () => {
            const ids = Array.from(selectedNodeIds);
            if (ids.length === 0) return { content: '' };
            try {
                const res = await apiClient.post(`/api/vaults/${vaultId}/nodes/content`, { node_ids: ids });
                return res.data;
            } catch (apiError) {
                throw new Error(apiError.response?.data?.error || 'Could not load node content from server.');
            }
        };

        try {
            await copyContextContent(getContextContentForApi);
            setCopyContentStatus('success');
            setTimeout(() => setCopyContentStatus('idle'), 2000);
        } catch (error) {
            setCopyContentError(error.message);
            setCopyContentStatus('error');
        }
    }, [selectedNodeIds, vaultId]);

    // UPDATED: Now uses the `agent_tree` endpoint for lightning-fast summary fetching
    const handleCopyTree = useCallback(async () => {
        setCopyTreeStatus('copying');
        setCopyTreeError(null);
        try {
            let nodesToProcess = treeData;

            // If summaries are requested, fetch the cached agent tree!
            if (includeSummary) {
                const res = await apiClient.get(`/api/vaults/${vaultId}/nodes`, {
                    params: { format: 'agent_tree' }
                });
                // Assuming the backend returns { tree: [...], allNodesFlat: [...] }
                nodesToProcess = res.data.tree || res.data;
            }

            // Recursive function to format the tree text
            const buildText = (nodes, depth = 0) => {
                let text = '';
                const indent = '  '.repeat(depth);

                for (const node of nodes) {
                    text += `${indent}- ${node.title}`;
                    if (includeUuid) {
                        text += ` (${node.id})`;
                    }
                    text += '\n';

                    if (includeSummary && node.ai_summary) {
                        const summaryIndent = '  '.repeat(depth + 1);
                        // Ensure multi-line summaries stay nicely indented under the arrow
                        const formattedSummary = node.ai_summary.replace(/\n/g, `\n${summaryIndent}  `);
                        text += `${summaryIndent}↳ ${formattedSummary}\n`;
                    }

                    if (node.children && node.children.length > 0) {
                        text += buildText(node.children, depth + 1);
                    }
                }
                return text;
            };

            const textToCopy = buildText(nodesToProcess);
            await navigator.clipboard.writeText(textToCopy);

            setCopyTreeStatus('success');
            setTimeout(() => setCopyTreeStatus('idle'), 2000);
        } catch (error) {
            setCopyTreeError(error.message || "Failed to copy tree structure.");
            setCopyTreeStatus('error');
        }
    }, [treeData, vaultId, includeUuid, includeSummary]);

    const handlePrintSelected = useCallback(async () => {
        if (!hasSelection) return;
        setPrintStatus('preparing');
        setPrintError(null);

        try {
            const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
            const nodes = await getFullNodesByIds(orderedIds, vaultId);
            const toc = generateTocForSelectedNodes(treeData, selectedNodeIds);

            openPrintPreview(nodes, toc);

            setPrintStatus('idle');
        } catch (error) {
            setPrintError('Failed to prepare print preview. ' + error.message);
            setPrintStatus('error');
        }
    }, [treeData, selectedNodeIds, vaultId, openPrintPreview, hasSelection]);

    const handlePrintAll = useCallback(async () => {
        if (!hasNodes) return;
        setPrintStatus('preparing_all');
        setPrintError(null);

        try {
            const allNodeIdsSet = new Set(allNodesFlat.map(n => n.id));
            const orderedIds = getIdsInOrder(treeData, allNodeIdsSet);
            const nodes = await getFullNodesByIds(orderedIds, vaultId);
            const toc = generateTocForSelectedNodes(treeData, allNodeIdsSet);

            openPrintPreview(nodes, toc);

            setPrintStatus('idle');
        } catch (error) {
            setPrintError('Failed to prepare print preview for entire vault. ' + error.message);
            setPrintStatus('error');
        }
    }, [treeData, allNodesFlat, vaultId, openPrintPreview, hasNodes]);

    const isPrinting = printStatus === 'preparing' || printStatus === 'preparing_all';

    return (
        <div className="p-3 d-flex flex-column gap-3">
            <div>
                <h6 className="text-muted mb-2">Tools & Export</h6>

                {/* EXACT COPY OF THE AGENT TAB UI FOR SELECTED NODES */}
                <div className="mb-3">
                    <small className="text-muted fw-bold d-block mb-1">
                        Selected nodes ({selectedNodes.length})
                    </small>
                    {selectedNodes.length === 0 ? (
                        <small className="text-muted fst-italic">
                            No nodes selected — use the tree to select nodes
                        </small>
                    ) : (
                        <div className="agent-context-list">
                            {selectedNodes.map(n => (
                                <span key={n.id} className="agent-context-chip" title={n.id}>
                                    {n.title}
                                </span>
                            ))}
                        </div>
                    )}
                </div>

                <div className="d-grid gap-2">
                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={handlePrintSelected}
                        disabled={!hasSelection || isPrinting}
                    >
                        <i className="bx bx-printer me-1"></i>
                        {printStatus === 'preparing' ? 'Preparing Print...' : 'Print Selected Nodes'}
                    </Button>

                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={handlePrintAll}
                        disabled={!hasNodes || isPrinting}
                    >
                        <i className="bx bxs-book-content me-1"></i>
                        {printStatus === 'preparing_all' ? 'Preparing Entire Vault...' : 'Print Entire Vault'}
                    </Button>

                    <hr className="my-2 text-muted" />

                    <h6 className="text-muted mb-2">Copy to Clipboard</h6>

                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={handleCopyContent}
                        disabled={!hasSelection || copyContentStatus === 'copying'}
                    >
                        <i className="bx bx-copy-alt me-1"></i>
                        {copyContentStatus === 'copying' && 'Copying…'}
                        {copyContentStatus === 'success' && '✓ Copied!'}
                        {(copyContentStatus === 'idle' || copyContentStatus === 'error') && 'Copy Content'}
                    </Button>

                    <div className="mt-3 px-1">
                        <Form.Check
                            type="switch"
                            id="toggle-uuid"
                            label={<small className="text-muted">Include UUIDs</small>}
                            checked={includeUuid}
                            onChange={(e) => setIncludeUuid(e.target.checked)}
                        />
                        <Form.Check
                            type="switch"
                            id="toggle-summary"
                            label={<small className="text-muted">Include AI Summaries</small>}
                            checked={includeSummary}
                            onChange={(e) => setIncludeSummary(e.target.checked)}
                        />
                    </div>

                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={handleCopyTree}
                        disabled={copyTreeStatus === 'copying'}
                    >
                        <i className="bx bx-list-tree me-1"></i>
                        {copyTreeStatus === 'copying' && 'Copying…'}
                        {copyTreeStatus === 'success' && '✓ Copied!'}
                        {(copyTreeStatus === 'idle' || copyTreeStatus === 'error') && 'Copy Full Tree Structure'}
                    </Button>
                </div>
            </div>

            {/* Error Alerts */}
            {printError && (
                <Alert variant="danger" className="mt-2 small p-2">
                    <strong>Error:</strong> {printError}
                </Alert>
            )}
            {copyContentError && (
                <Alert variant="danger" className="mt-2 small p-2">
                    <strong>Error:</strong> {copyContentError}
                </Alert>
            )}
            {copyTreeError && (
                <Alert variant="danger" className="mt-2 small p-2">
                    <strong>Error:</strong> {copyTreeError}
                </Alert>
            )}
        </div>
    );
}