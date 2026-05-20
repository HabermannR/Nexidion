// src/features/workspace/ToolsTab.jsx

import React, { useState, useCallback, useMemo, useRef } from 'react';
import { Button, Form } from 'react-bootstrap';
import { useParams } from 'react-router-dom';

import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { copyContextContent } from '../../lib/clipboardService.js';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';
import { useToast } from '../../components/ToastProvider.jsx';

// Import our helper functions
import { getIdsInOrder, generateTocForSelectedNodes } from '../nodes/node.utils.js';
import { getFullNodesByIds } from '../../lib/exportService.js';

// Import the Agent styles so our chips look exactly the same!
import '../agent/AgentTab.css';

export default function ToolsTab() {
    const { vaultId } = useParams();
    const toast = useToast();

    const [copyContentStatus, setCopyContentStatus] = useState('idle'); // idle | copying | success
    const [copyTreeStatus, setCopyTreeStatus] = useState('idle');
    const [printStatus, setPrintStatus] = useState('idle'); // idle | preparing | preparing_all
    const [exportStatus, setExportStatus] = useState('idle'); // idle | exporting | success
    const [importStatus, setImportStatus] = useState('idle'); // idle | importing | success
    const [ingestStatus, setIngestStatus] = useState('idle'); // idle | ingesting

    // Toggles for Copy Tree
    const [includeUuid, setIncludeUuid] = useState(true);
    const [includeSummary, setIncludeSummary] = useState(false);

    const fileInputRef = useRef(null);
    const pdfInputRef = useRef(null); // Dedicated ref for PDF Ingestion

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

    // Calculate Ingestion Target Logic
    const isIngestAllowed = selectedNodes.length <= 1;
    const ingestTargetId = selectedNodes.length === 1 ? selectedNodes[0].id : '';
    const ingestTargetTitle = selectedNodes.length === 1 ? selectedNodes[0].title : 'Vault Root';

    const handleCopyContent = useCallback(async () => {
        setCopyContentStatus('copying');

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
            toast.error(`Copy failed: ${error.message}`);
            setCopyContentStatus('idle');
        }
    }, [selectedNodeIds, vaultId, toast]);

    const handleCopyTree = useCallback(async () => {
        setCopyTreeStatus('copying');
        try {
            let nodesToProcess = treeData;

            if (includeSummary) {
                const res = await apiClient.get(`/api/vaults/${vaultId}/nodes`, {
                    params: { format: 'agent_tree' }
                });
                nodesToProcess = res.data.tree || res.data;
            }

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
            toast.error(`Copy failed: ${error.message || 'Failed to copy tree structure.'}`);
            setCopyTreeStatus('idle');
        }
    }, [treeData, vaultId, includeUuid, includeSummary, toast]);

    const handlePrintSelected = useCallback(async () => {
        if (!hasSelection) return;
        setPrintStatus('preparing');

        try {
            const orderedIds = getIdsInOrder(treeData, selectedNodeIds);
            const nodes = await getFullNodesByIds(orderedIds, vaultId);
            const toc = generateTocForSelectedNodes(treeData, selectedNodeIds);
            openPrintPreview(nodes, toc);
            setPrintStatus('idle');
        } catch (error) {
            toast.error(`Failed to prepare print preview: ${error.message}`);
            setPrintStatus('idle');
        }
    }, [treeData, selectedNodeIds, vaultId, openPrintPreview, hasSelection, toast]);

    const handlePrintAll = useCallback(async () => {
        if (!hasNodes) return;
        setPrintStatus('preparing_all');

        try {
            const allNodeIdsSet = new Set(allNodesFlat.map(n => n.id));
            const orderedIds = getIdsInOrder(treeData, allNodeIdsSet);
            const nodes = await getFullNodesByIds(orderedIds, vaultId);
            const toc = generateTocForSelectedNodes(treeData, allNodeIdsSet);
            openPrintPreview(nodes, toc);
            setPrintStatus('idle');
        } catch (error) {
            toast.error(`Failed to prepare print preview: ${error.message}`);
            setPrintStatus('idle');
        }
    }, [treeData, allNodesFlat, vaultId, openPrintPreview, hasNodes, toast]);

    const handleExportVault = useCallback(async () => {
        setExportStatus('exporting');
        try {
            const response = await apiClient.get(`/api/vaults/${vaultId}/export`, {
                responseType: 'blob'
            });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;

            let filename = `vault-${vaultId}.nexidion`;
            const disposition = response.headers['content-disposition'];
            if (disposition && disposition.indexOf('filename=') !== -1) {
                const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                const matches = filenameRegex.exec(disposition);
                if (matches != null && matches[1]) {
                    filename = matches[1].replace(/['"]/g, '');
                }
            }

            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.parentNode.removeChild(link);
            window.URL.revokeObjectURL(url);

            setExportStatus('success');
            setTimeout(() => setExportStatus('idle'), 2000);
        } catch (error) {
            let errorMsg = 'Failed to export vault.';
            if (error.response?.data instanceof Blob) {
                try {
                    const text = await error.response.data.text();
                    const json = JSON.parse(text);
                    if (json.error) errorMsg = json.error;
                } catch (e) { /* ignore */ }
            } else if (error.response?.data?.error) {
                errorMsg = error.response.data.error;
            } else if (error.message) {
                errorMsg = error.message;
            }
            toast.error(`Export failed: ${errorMsg}`);
            setExportStatus('idle');
        }
    }, [vaultId, toast]);

    const handleImportClick = () => {
        if (fileInputRef.current) fileInputRef.current.click();
    };

    const handleFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setImportStatus('importing');

        const formData = new FormData();
        formData.append('file', file);

        try {
            await apiClient.post('/api/vaults/import', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            setImportStatus('success');

            setTimeout(() => {
                setImportStatus('idle');
                window.location.reload();
            }, 2500);
        } catch (error) {
            const errorMsg = error.response?.data?.error || error.message || 'Failed to import vault.';
            toast.error(`Import failed: ${errorMsg}`);
            setImportStatus('idle');
        } finally {
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    const handlePdfIngestClick = () => {
        if (pdfInputRef.current) pdfInputRef.current.click();
    };

    const handlePdfFileChange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setIngestStatus('ingesting');
        const formData = new FormData();
        formData.append('file', file);
        if (ingestTargetId) {
            formData.append('parent_id', ingestTargetId);
        }

        try {
            await apiClient.post(`/api/vaults/${vaultId}/ingest/pdf`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            toast.success('PDF ingestion started! The document will appear in your tree automatically once finished.');
        } catch (error) {
            const errorMsg = error.response?.data?.error || error.message || 'Failed to ingest PDF.';
            toast.error(`Ingestion failed: ${errorMsg}`);
        } finally {
            setIngestStatus('idle');
            if (pdfInputRef.current) {
                pdfInputRef.current.value = '';
            }
        }
    };

    const isPrinting = printStatus === 'preparing' || printStatus === 'preparing_all';

    return (
        <div className="p-3 d-flex flex-column gap-3">
            <div>
                <h6 className="text-muted mb-2">Tools & Export</h6>

                {/* SELECTED NODES LIST */}
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

                    {/* NEW: AI INGESTION SECTION */}
                    <hr className="my-2 text-muted" />
                    <h6 className="text-muted mb-2">AI Document Ingestion</h6>

                    <input
                        type="file"
                        accept=".pdf"
                        style={{ display: 'none' }}
                        ref={pdfInputRef}
                        onChange={handlePdfFileChange}
                    />

                    <Button
                        variant="outline-info"
                        size="sm"
                        onClick={handlePdfIngestClick}
                        disabled={!isIngestAllowed || ingestStatus === 'ingesting'}
                    >
                        {ingestStatus === 'ingesting' ? (
                            <><i className="bx bx-loader-alt bx-spin me-1"></i> Uploading...</>
                        ) : (
                            <><i className="bx bxs-file-pdf me-1"></i> Ingest PDF to {ingestTargetTitle}</>
                        )}
                    </Button>
                    {!isIngestAllowed && (
                        <small className="text-danger">
                            Please select exactly 1 node (or 0 nodes) to use as a target folder.
                        </small>
                    )}

                    <hr className="my-2 text-muted" />

                    <h6 className="text-muted mb-2">Vault Data</h6>

                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={handleExportVault}
                        disabled={exportStatus === 'exporting'}
                    >
                        <i className="bx bx-export me-1"></i>
                        {exportStatus === 'exporting' && 'Exporting...'}
                        {exportStatus === 'success' && '✓ Exported!'}
                        {(exportStatus === 'idle' || exportStatus === 'error') && 'Export Vault'}
                    </Button>

                    <input
                        type="file"
                        accept=".nexidion,.json"
                        style={{ display: 'none' }}
                        ref={fileInputRef}
                        onChange={handleFileChange}
                    />

                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={handleImportClick}
                        disabled={importStatus === 'importing'}
                    >
                        <i className="bx bx-import me-1"></i>
                        {importStatus === 'importing' && 'Importing...'}
                        {importStatus === 'success' && '✓ Imported! Reloading...'}
                        {(importStatus === 'idle' || importStatus === 'error') && 'Import Vault'}
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
        </div>
    );
}