import React, { useState, useCallback } from 'react';
import { Button, Alert } from 'react-bootstrap';
import { useParams } from 'react-router-dom';

import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import { copyContextContent, copyTreeStructure } from '../../lib/clipboardService.js';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';

export default function ToolsTab() {
    const { vaultId } = useParams();
    const [copyContentStatus, setCopyContentStatus] = useState('idle'); // idle | copying | success | error
    const [copyContentError, setCopyContentError] = useState(null);
    const [copyTreeStatus, setCopyTreeStatus] = useState('idle');
    const [copyTreeError, setCopyTreeError] = useState(null);

    const { data } = useVaultTreeQuery(vaultId);
    const treeData = data?.tree || [];
    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const hasSelection = selectedNodeIds.size > 0;

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

    const handleCopyTree = useCallback(async () => {
        setCopyTreeStatus('copying');
        setCopyTreeError(null);
        try {
            await copyTreeStructure(treeData);
            setCopyTreeStatus('success');
            setTimeout(() => setCopyTreeStatus('idle'), 2000);
        } catch (error) {
            setCopyTreeError(error.message);
            setCopyTreeStatus('error');
        }
    }, [treeData]);

    return (
        <div className="p-3">
            <h6 className="text-muted">Copy to Clipboard</h6>
            <div className="d-grid gap-2">
                <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={handleCopyContent}
                    disabled={!hasSelection || copyContentStatus === 'copying'}
                >
                    {copyContentStatus === 'copying' && 'Copying…'}
                    {copyContentStatus === 'success' && '✓ Copied!'}
                    {(copyContentStatus === 'idle' || copyContentStatus === 'error') && (
                        hasSelection
                            ? `Copy Content of ${selectedNodeIds.size} Node(s)`
                            : 'Copy Content (select nodes first)'
                    )}
                </Button>
                <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={handleCopyTree}
                    disabled={copyTreeStatus === 'copying'}
                >
                    {copyTreeStatus === 'copying' && 'Copying…'}
                    {copyTreeStatus === 'success' && '✓ Copied!'}
                    {(copyTreeStatus === 'idle' || copyTreeStatus === 'error') && 'Copy Full Tree Structure'}
                </Button>
            </div>
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
