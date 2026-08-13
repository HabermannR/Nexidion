// src/features/agent/AgentTab.jsx
import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useParams, NavLink } from 'react-router-dom';
import { Button, Form } from 'react-bootstrap';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useWorkspaceStore } from '../workspace/workspaceStore';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';
import apiClient from '../../api/apiClient';
import { useToast } from '../../components/ToastProvider';

import './AgentTab.css';

// ─── Constants ────────────────────────────────────────────────────────────────

const OPERATION_META = {
    create_node:             { label: 'Created node',  color: 'var(--agent-op-create, #2e7d5e)', icon: '✦' },
    patch_node:              { label: 'Patched node',  color: 'var(--primary-color, #405d83)', icon: '✎' },
    write_node:              { label: 'Wrote node',    color: 'var(--agent-op-write, #2e6b7d)', icon: '▤' },
    write_node_summary_only: { label: 'Summary only',  color: 'var(--agent-op-summary, #888888)', icon: '◎' },
    delete_node:             { label: 'Deleted node',  color: 'var(--agent-op-delete, #a03535)', icon: '✕' },
    move_node:               { label: 'Moved node',    color: 'var(--agent-op-move, #7a6020)', icon: '⇢' },
};

// How many minutes before a "processing" task is considered stale/stuck.
const STUCK_THRESHOLD_MINUTES = 10;
const CUSTOM_MODEL_VALUE = '__custom__';

function formatTokenPrice(value) {
    if (value === null || value === undefined) return 'price unavailable';
    const digits = value < 0.01 ? 4 : value < 1 ? 2 : value < 10 ? 2 : 0;
    return `$${Number(value).toFixed(digits)}`;
}

const ACTIONS = [
    {
        id: 'bubble-up',
        icon: '↑',
        title: 'Roll up branch knowledge',
        description: 'Select a parent. Rewrite it and its non-leaf descendants from existing child knowledge, bottom-up.',
        impact: 'Leaves stay unchanged. Parent notes and their AI summaries are rewritten from the deepest parent upward, finishing at each selected root. Structure stays unchanged.',
        confirmLabel: 'Selected destination root',
        buttonLabel: 'Roll up to selected root',
        instruction: `Roll up knowledge bottom-up for every selected context node, treating each selected node as the destination root of its branch.

For each subtree:
1. Use get_subtree to discover the complete hierarchy.
2. Identify leaves and non-leaf parents. Leaves are source material only: do not call write_node, patch_node, rename_node, move_node, or any other write tool on a leaf. Do not change a leaf's content, title, summary, version, or location.
3. Process only non-leaf nodes, deepest first and each selected root last. For each parent, read its immediate children's current content or summaries. Children that are themselves parents will already contain the newly rolled-up result from the previous step.
4. Rewrite the parent's Markdown content as a useful, coherent synthesis of the knowledge in its immediate children. Preserve important existing parent context when it remains relevant; do not merely concatenate summaries.
5. In the same write_node call, set the parent's ai_summary to exactly three useful bullet points beginning with "- ". Both content and summary must be updated for every accessible non-leaf node in scope.
6. Do not create, delete, move, rename, or reorganize nodes. Skip private or write-protected parents that cannot be updated and mention them in the final result.

If a selected root is a leaf, leave it unchanged and report that it has no child knowledge to roll up. Finish with the number of parent notes updated, confirmation that leaves were unchanged, and any nodes skipped.`,
    },
    {
        id: 'refresh-selected',
        icon: '✦',
        title: 'Refresh selected summaries',
        description: 'Regenerate concise summaries for the selected nodes only.',
        impact: 'Updates only the selected nodes’ AI summaries. Children, note content, and structure stay unchanged.',
        buttonLabel: 'Refresh summaries',
        instruction: `Refresh the AI summary of each selected context node, and only those nodes.

Read each selected node's content and replace its ai_summary with exactly three useful bullet points beginning with "- ". Use patch_node with an empty patches array so Markdown content is unchanged. Do not process descendants unless they are separately selected. Do not create, delete, move, rename, or reorganize nodes. Skip private nodes that cannot be read and mention them in the final result.

Finish with the number of summaries updated and any nodes skipped.`,
    },
    {
        id: 'improve-titles',
        icon: '✎',
        title: 'Improve unclear titles',
        description: 'Review selected nodes and rename only titles that are vague or misleading.',
        impact: 'May rename selected nodes. Note content, summaries, children, and locations stay unchanged.',
        buttonLabel: 'Review titles',
        instruction: `Review the titles of the selected context nodes, and only those nodes.

Read enough of each selected node to judge whether its title is vague, generic, or misleading. Rename a node only when a clearer, concise title is strongly supported by its content. Leave already useful titles unchanged. Do not modify content or AI summaries, and do not create, delete, move, or reorganize any nodes. Do not process descendants unless they are separately selected.

Finish with a list of renamed nodes and explicitly state when no rename was needed.`,
    },
];

// ─── OperationDetail ──────────────────────────────────────────────────────────

function OperationDetail({ detail }) {
    if (!detail || typeof detail !== 'object') return null;
    const entries = Object.entries(detail);
    if (entries.length === 0) return null;

    return (
        <div className="agent-op-detail">
            {entries.map(([k, v]) => {
                const isLong = typeof v === 'string' && v.length > 80;
                return (
                    <div key={k} className="agent-op-detail-row">
                        <span className="agent-op-detail-key">
                            {k.replace(/_/g, ' ')}
                        </span>
                        <span className={`agent-op-detail-val ${isLong ? 'is-long' : 'is-short'}`}>
                            {typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v)}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

// ─── OperationRow ─────────────────────────────────────────────────────────────

function OperationRow({ op, vaultId }) {
    const [open, setOpen] = useState(false);
    const meta = OPERATION_META[op.operation] || { label: op.operation, color: 'var(--text-muted, #6c757d)', icon: '●' };
    const time = op.timestamp
        ? new Date(op.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        : '';
    const hasDetail = op.detail && Object.keys(op.detail).length > 0;
    const shortId = String(op.node_id || '').substring(0, 8);

    return (
        <div className="agent-op-row" style={{ '--op-color': meta.color }}>
            <div
                className={`agent-op-row-header ${hasDetail ? 'clickable' : ''}`}
                onClick={() => hasDetail && setOpen(o => !o)}
            >
                <span className="agent-op-label">
                    {meta.icon} {meta.label}
                </span>
                {op.node_id && vaultId ? (
                    <NavLink
                        to={`/vaults/${vaultId}/nodes/${op.node_id}`}
                        className="agent-op-link"
                        onClick={e => e.stopPropagation()}
                    >
                        {shortId}
                    </NavLink>
                ) : (
                    <span className="agent-op-id">{shortId}</span>
                )}
                <span className="agent-op-time">{time}</span>
                {hasDetail && (
                    <span className="agent-op-toggle">{open ? '▲' : '▼'}</span>
                )}
            </div>
            {open && hasDetail && <OperationDetail detail={op.detail} />}
        </div>
    );
}

// ─── StuckWarning ─────────────────────────────────────────────────────────────

function StuckWarning({ createdAt }) {
    const ageMinutes = (Date.now() - new Date(createdAt).getTime()) / 60_000;
    if (ageMinutes < STUCK_THRESHOLD_MINUTES) return null;
    return (
        <div className="agent-stuck-warning">
            ⚠ Still processing after {Math.floor(ageMinutes)} min — the runner may have stalled.
        </div>
    );
}

// ─── RetryButton ──────────────────────────────────────────────────────────────

function RetryButton({ task, vaultId }) {
    const queryClient = useQueryClient();
    const toast = useToast();

    const retryMutation = useMutation({
        mutationFn: () =>
            apiClient.post('/api/tasks', {
                vault_id: parseInt(vaultId),
                instruction: task.instruction,
                context_node_ids: task.context_node_ids || [],
                llm_provider: task.llm_provider || undefined,
                llm_model: task.llm_model || undefined,
            }),
        onSuccess: () => {
            toast.success('Task re-queued');
            queryClient.invalidateQueries({ queryKey: ['agentTasks', vaultId] });
        },
        onError: (err) => {
            toast.error(err.response?.data?.error || 'Failed to re-queue task.');
        },
    });

    return (
        <button
            className="agent-retry-btn"
            disabled={retryMutation.isPending}
            onClick={(e) => {
                e.stopPropagation();
                retryMutation.mutate();
            }}
            title="Re-queue this task with the same instruction and context"
        >
            {retryMutation.isPending ? '…' : '↺ Retry'}
        </button>
    );
}

// ─── TaskDetail — fetched on expand ──────────────────────────────────────────

function TaskDetail({ taskId, vaultId, taskStatus }) {
    const isLive = taskStatus === 'processing';

    const { data, isLoading, isError } = useQuery({
        queryKey: ['agentTask', taskId],
        queryFn: async () => {
            const res = await apiClient.get(`/api/tasks/${taskId}`);
            return res.data;
        },
        staleTime: isLive ? 0 : 10_000,
        // Poll every 2s while processing so step messages appear live.
        refetchInterval: isLive ? 2000 : false,
    });

    if (isLoading) return <div className="text-muted small py-2">Loading…</div>;
    if (isError || !data) return <div className="text-danger small py-2">Failed to load detail.</div>;

    const operations = Array.isArray(data.operations) ? data.operations : [];

    return (
        <div className="agent-task-detail-container">
            <div>
                <div className="agent-task-section-title">Input</div>
                <div className="agent-task-box is-input">
                    {data.instruction || <span className="text-muted">—</span>}
                </div>
                {(data.llm_provider || data.llm_model) && (
                    <div className="agent-task-model">
                        {data.llm_provider || 'legacy default'} · {data.llm_model || 'default model'}
                    </div>
                )}
            </div>

            <div>
                <div className="agent-task-section-title">
                    {isLive ? '⟳ In progress' : 'Output'}
                </div>
                <div className="agent-task-box">
                    {data.finish_summary
                        ? data.finish_summary
                        : <span className="text-muted fst-italic">{isLive ? 'Starting…' : 'No output yet'}</span>
                    }
                </div>
            </div>

            <div>
                <div className="agent-task-section-title">
                    Operations ({operations.length})
                </div>
                {operations.length === 0 ? (
                    <div className="text-muted small fst-italic">No write operations recorded.</div>
                ) : (
                    <div className="d-flex flex-column gap-1">
                        {operations.map((op, i) => (
                            <OperationRow key={i} op={op} vaultId={vaultId} />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
    const statusClass = `status-${(status || 'pending').toLowerCase()}`;
    return (
        <span className={`agent-status-badge ${statusClass}`}>
            {status}
        </span>
    );
}

// ─── TaskCard ─────────────────────────────────────────────────────────────────

function TaskCard({ task, vaultId }) {
    const [expanded, setExpanded] = useState(false);
    const preview = task.preview_text || task.instruction || '';

    const isFailed     = task.status === 'failed';
    const isProcessing = task.status === 'processing';

    return (
        <div className={`agent-task-card ${expanded ? 'expanded' : ''} ${isFailed ? 'is-failed' : ''}`}>
            <div
                className="agent-task-card-header"
                onClick={() => setExpanded(e => !e)}
            >
                <div className="d-flex gap-2 align-items-start">
                    <div className={`agent-task-card-preview ${!expanded ? 'is-collapsed' : ''}`}>
                        {preview}
                    </div>
                    <div className="d-flex flex-column align-items-end gap-1">
                        <StatusBadge status={task.status} />
                        {/* Retry button — shown for failed tasks AND in the header for stuck-processing */}
                        {(isFailed || isProcessing) && (
                            <RetryButton task={task} vaultId={vaultId} />
                        )}
                    </div>
                </div>

                <div className="agent-task-card-meta">
                    <span
                        className="agent-task-card-id"
                        title={task.id}
                        style={{ cursor: 'pointer' }}
                        onClick={(e) => {
                            e.stopPropagation();
                            navigator.clipboard.writeText(task.id).catch(() => {});
                        }}
                    >
                        {String(task.id).substring(0, 8)}&thinsp;⎘
                    </span>
                    <div className="d-flex gap-2 align-items-center">
                        {task.created_at && (
                            <span className="agent-task-card-time">
                                {new Date(task.created_at).toLocaleString()}
                            </span>
                        )}
                        <span className="agent-task-card-time" style={{ fontSize: '0.6rem' }}>
                            {expanded ? '▲' : '▼'}
                        </span>
                    </div>
                </div>

                {/* Stuck-processing warning (shown inline, not in the detail pane) */}
                {isProcessing && (
                    <StuckWarning createdAt={task.created_at} />
                )}
            </div>

            {expanded && (
                <div className="agent-task-card-body">
                    <TaskDetail taskId={task.id} vaultId={vaultId} taskStatus={task.status} />
                </div>
            )}
        </div>
    );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AgentTab() {
    const { vaultId, nodeId } = useParams();
    const queryClient = useQueryClient();
    const toast = useToast();
    const [pendingAction, setPendingAction] = useState(null);
    const [excludedRollupNodeIds, setExcludedRollupNodeIds] = useState(() => new Set());
    const [statusFilter, setStatusFilter] = useState('');
    const [llmProvider, setLlmProvider] = useState(() => localStorage.getItem('nexidion-task-provider') || '');
    const [llmModel, setLlmModel] = useState(() => localStorage.getItem('nexidion-task-model') || '');

    const { data: systemConfig } = useQuery({
        queryKey: ['systemConfig'],
        queryFn: () => apiClient.get('/api/system/config').then(res => res.data),
        staleTime: 60_000,
    });
    const providerConfig = useMemo(
        () => systemConfig?.task_providers || systemConfig?.llm_providers || systemConfig?.summary_providers || {},
        [systemConfig],
    );
    const availableProviders = useMemo(() => Object.entries(providerConfig)
        .filter(([, config]) => config?.configured)
        .map(([id, config]) => ({
            id,
            label: config.label || ({ local: 'Local', openai: 'OpenAI', openrouter: 'OpenRouter' }[id] || id),
            models: Array.isArray(config.models) && config.models.length
                ? config.models
                : [config.default_model || config.model].filter(Boolean),
            defaultModel: config.default_model || config.model || '',
            supportsCustomModel: Boolean(config.supports_custom_model),
        })), [providerConfig]);
    const selectedProvider = availableProviders.find(provider => provider.id === llmProvider);
    const { data: openRouterCatalog } = useQuery({
        queryKey: ['openrouterModels'],
        queryFn: () => apiClient.get('/api/system/openrouter-models').then(res => res.data),
        enabled: llmProvider === 'openrouter',
        staleTime: 5 * 60_000,
        retry: 1,
    });
    const curatedModels = llmProvider === 'openrouter'
        ? (openRouterCatalog?.models || [])
        : (selectedProvider?.models || []).map(id => ({ id, name: id }));
    const selectedCatalogModel = curatedModels.find(model => model.id === llmModel);
    const usesCustomModel = Boolean(selectedProvider?.supportsCustomModel && llmModel && !selectedCatalogModel);

    useEffect(() => {
        if (!availableProviders.length) return;
        const provider = availableProviders.find(item => item.id === llmProvider) || availableProviders[0];
        if (provider.id !== llmProvider) setLlmProvider(provider.id);
        if (!llmModel || (!provider.supportsCustomModel && provider.models.length && !provider.models.includes(llmModel))) {
            setLlmModel(provider.defaultModel || provider.models[0] || '');
        }
    }, [availableProviders, llmProvider, llmModel]);

    useEffect(() => {
        if (llmProvider) localStorage.setItem('nexidion-task-provider', llmProvider);
        if (llmModel) localStorage.setItem('nexidion-task-model', llmModel);
    }, [llmProvider, llmModel]);

    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const isEditingNode = useWorkspaceStore(state => state.isEditingNode);
    const { data: queryData } = useVaultTreeQuery(vaultId);
    const allNodesFlat = useMemo(() => queryData?.allNodesFlat || [], [queryData]);

    const selectedNodes = useMemo(() => {
        if (allNodesFlat.length === 0 || selectedNodeIds.size === 0) return [];
        const nodeMap = new Map(allNodesFlat.map(n => [n.id, n]));
        return Array.from(selectedNodeIds)
            .map(id => ({ id, title: nodeMap.get(id)?.title || id }))
            .sort((a, b) => a.title.localeCompare(b.title));
    }, [selectedNodeIds, allNodesFlat]);

    const rollupPreview = useMemo(() => {
        if (pendingAction?.id !== 'bubble-up') return { parents: [], leafCount: 0 };
        const selectedIds = new Set(selectedNodeIds);
        const parents = new Map();
        const leaves = new Set();
        const visit = (node, depth = 0, insideRoot = false) => {
            const inScope = insideRoot || selectedIds.has(node.id);
            const children = Array.isArray(node.children) ? node.children : [];
            if (inScope) {
                if (children.length) parents.set(node.id, {
                    id: node.id, title: node.title, depth,
                    writeAllowed: node.write_allowed !== false,
                });
                else leaves.add(node.id);
            }
            children.forEach(child => visit(child, depth + 1, inScope));
        };
        (queryData?.tree || []).forEach(node => visit(node));
        return {
            parents: Array.from(parents.values()).sort((a, b) => b.depth - a.depth || a.title.localeCompare(b.title)),
            leafCount: leaves.size,
        };
    }, [pendingAction, queryData?.tree, selectedNodeIds]);

    useEffect(() => {
        setExcludedRollupNodeIds(new Set());
    }, [pendingAction, selectedNodeIds]);


    const { data: tasks = [], isLoading: loadingTasks } = useQuery({
        queryKey: ['agentTasks', vaultId, statusFilter],
        queryFn: async () => {
            const params = { vault_id: vaultId, limit: 20 };
            if (statusFilter) params.status = statusFilter;
            const res = await apiClient.get('/api/tasks', { params });
            return Array.isArray(res.data) ? res.data : (res.data.tasks || []);
        },
        // Poll fast when something is actively running, slow when idle.
        // The function form re-evaluates against the latest cached data each cycle.
        refetchInterval: (query) => {
            const current = query.state.data ?? [];
            const active = current.some(t => t.status === 'processing' || t.status === 'pending');
            return active ? 3000 : 5000;
        },
    });

    // Track previous task statuses so we can detect completions.
    const prevTaskStatusesRef = useRef({});
    useEffect(() => {
        if (!tasks.length) return;

        const prev = prevTaskStatusesRef.current;
        let anyJustCompleted = false;

        tasks.forEach(task => {
            const wasProcessing = prev[task.id] && prev[task.id] !== 'completed' && prev[task.id] !== 'failed';
            const isNowDone = task.status === 'completed' || task.status === 'failed';
            if (wasProcessing && isNowDone && task.status === 'completed') {
                anyJustCompleted = true;
            }
        });

        // Update the ref with current statuses for next comparison.
        prevTaskStatusesRef.current = Object.fromEntries(tasks.map(t => [t.id, t.status]));

        if (anyJustCompleted) {
            // Refresh the vault tree so new/moved/deleted nodes appear immediately.
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            // Reload the open node's content — but not if the user is mid-edit,
            // which would silently discard their unsaved changes.
            if (nodeId && !isEditingNode) {
                queryClient.invalidateQueries({ queryKey: ['nodeContent', vaultId, nodeId] });
                queryClient.invalidateQueries({ queryKey: ['versions', vaultId, nodeId] });
            }
        }
    }, [tasks, vaultId, nodeId, isEditingNode, queryClient]);

    const queueMutation = useMutation({
        mutationFn: async (action) => {
            const jobs = action.jobs || [{
                instruction: action.instruction,
                contextNodeIds: Array.from(selectedNodeIds),
            }];
            if (action.jobs) {
                return apiClient.post('/api/tasks/batch', {
                    vault_id: parseInt(vaultId),
                    llm_provider: llmProvider,
                    llm_model: llmModel,
                    jobs: jobs.map(job => ({
                        instruction: job.instruction,
                        context_node_ids: job.contextNodeIds,
                        allowed_write_node_ids: job.allowedWriteNodeIds,
                        allowed_write_operations: ['write_node'],
                    })),
                });
            }
            const responses = [];
            for (const job of jobs) {
                responses.push(await apiClient.post('/api/tasks', {
                    vault_id: parseInt(vaultId),
                    instruction: job.instruction,
                    context_node_ids: job.contextNodeIds,
                    llm_provider: llmProvider,
                    llm_model: llmModel,
                    ...(job.allowedWriteNodeIds ? {
                        allowed_write_node_ids: job.allowedWriteNodeIds,
                        allowed_write_operations: ['write_node'],
                    } : {}),
                }));
            }
            return responses;
        },
        onSuccess: (_, action) => {
            setPendingAction(null);
            toast.success(`${action.title} added to queue`);
            queryClient.invalidateQueries({ queryKey: ['agentTasks', vaultId] });
        },
        onError: (err) => {
            const msg = err.response?.data?.error;
            if (err.response?.status === 403) {
                toast.error(msg || "You don't have permission to submit tasks in this vault.");
            } else if (err.response?.status === 429) {
                toast.error('Too many tasks — please wait before submitting again.');
            } else {
                toast.error(msg || 'Failed to queue action — check your connection.');
            }
        },
    });

    const handleConfirmAction = async () => {
        if (!pendingAction || selectedNodes.length === 0 || !llmProvider || !llmModel || queueMutation.isPending) return;
        let queuedAction = pendingAction;
        if (pendingAction.id === 'bubble-up') {
            const included = rollupPreview.parents.filter(node => node.writeAllowed && !excludedRollupNodeIds.has(node.id));
            if (!included.length) {
                toast.error('Select at least one parent node to update.');
                return;
            }
            const excluded = rollupPreview.parents
                .filter(node => !node.writeAllowed || excludedRollupNodeIds.has(node.id))
                .map(node => `${node.title} (${node.id})`).join(', ') || '(none)';
            queuedAction = {
                ...pendingAction,
                title: `${pendingAction.title} (${included.length} parent jobs)`,
                jobs: included.map((node, index) => ({
                    contextNodeIds: [node.id],
                    allowedWriteNodeIds: [node.id],
                    instruction: `Perform bounded roll-up job ${index + 1} of ${included.length}. Update exactly one parent: ${node.title} (${node.id}).

Use get_subtree, then fetch the full current Markdown content of this parent and every immediate child with get_node_content. This full-content evidence is mandatory; summaries alone are insufficient. The children are read-only source material and earlier jobs may already have refreshed their content. Rewrite this parent's Markdown as a coherent, useful synthesis that preserves still-relevant existing parent context. In the same write_node call, set exactly three useful AI-summary bullets beginning with "- ".

Do not write, patch, rename, move, create, or delete any other node. The only UUID permitted for a write is ${node.id}. Leaves and all descendants must remain unchanged. Parents excluded by the user from the overall roll-up: ${excluded}.

Finish after this one parent has been updated, or explain why it could not be updated.`,
                })),
            };
        }
        try {
            await queueMutation.mutateAsync(queuedAction);
        } catch {
            // The mutation displays the API error through the toast provider.
        }
    };

    return (
        <div className="agent-actions-panel p-3 d-flex flex-column gap-3">
            <div>
                <div className="agent-actions-heading">
                    <div>
                        <h6 className="mb-1">AI actions</h6>
                        <p>Run a focused background job. Use MCP for open-ended AI conversations.</p>
                    </div>
                    <span className="agent-worker-badge">Task runner</span>
                </div>

                <div className={`agent-context-box ${selectedNodes.length === 0 ? 'is-empty' : ''}`}>
                    <small className="agent-context-label">
                        Selected context <span>{selectedNodes.length}</span>
                    </small>
                    {selectedNodes.length === 0 ? (
                        <div className="agent-empty-context">
                            Select one or more nodes in the tree to enable actions.
                        </div>
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

                <div className="agent-model-selector">
                    <Form.Group>
                        <Form.Label>Provider</Form.Label>
                        <Form.Select size="sm" value={llmProvider} onChange={event => {
                            const next = availableProviders.find(item => item.id === event.target.value);
                            setLlmProvider(event.target.value);
                            setLlmModel(next?.defaultModel || next?.models[0] || '');
                        }} disabled={!availableProviders.length}>
                            {!availableProviders.length && <option value="">No provider configured</option>}
                            {availableProviders.map(provider => <option key={provider.id} value={provider.id}>{provider.label}</option>)}
                        </Form.Select>
                    </Form.Group>
                    <Form.Group>
                        <Form.Label>Model</Form.Label>
                        {curatedModels.length || selectedProvider?.supportsCustomModel ? (
                            <>
                                <Form.Select
                                    size="sm"
                                    value={usesCustomModel || !llmModel ? CUSTOM_MODEL_VALUE : llmModel}
                                    onChange={event => setLlmModel(event.target.value === CUSTOM_MODEL_VALUE ? '' : event.target.value)}
                                >
                                    {curatedModels.map(model => (
                                        <option key={model.id} value={model.id}>
                                            {model.name}{model.price_tier ? ` · ${model.price_tier}` : ''}
                                        </option>
                                    ))}
                                    {selectedProvider?.supportsCustomModel && <option value={CUSTOM_MODEL_VALUE}>Custom model…</option>}
                                </Form.Select>
                                {(usesCustomModel || !llmModel) && selectedProvider?.supportsCustomModel && (
                                    <Form.Control
                                        className="mt-1"
                                        size="sm"
                                        value={llmModel}
                                        onChange={event => setLlmModel(event.target.value)}
                                        placeholder="provider/model-id"
                                        aria-label="Custom model ID"
                                    />
                                )}
                                {selectedCatalogModel && (
                                    <div className="agent-model-price">
                                        <span className={`agent-price-tier tier-${selectedCatalogModel.price_tier?.toLowerCase() || 'unknown'}`}>
                                            {selectedCatalogModel.price_tier || 'Price unavailable'}
                                        </span>
                                        {selectedCatalogModel.input_price !== null && selectedCatalogModel.input_price !== undefined && (
                                            <span>{formatTokenPrice(selectedCatalogModel.input_price)} input / {formatTokenPrice(selectedCatalogModel.output_price)} output per 1M tokens</span>
                                        )}
                                    </div>
                                )}
                            </>
                        ) : (
                            <Form.Control size="sm" value={llmModel} onChange={event => setLlmModel(event.target.value)} placeholder="Model ID" />
                        )}
                    </Form.Group>
                </div>

                <div className="agent-action-grid" aria-label="Available AI actions">
                    {ACTIONS.map(action => (
                        <button
                            key={action.id}
                            type="button"
                            className={`agent-action-card ${pendingAction?.id === action.id ? 'is-selected' : ''}`}
                            onClick={() => setPendingAction(action)}
                            disabled={selectedNodes.length === 0 || !llmProvider || !llmModel || queueMutation.isPending}
                        >
                            <span className="agent-action-icon" aria-hidden="true">{action.icon}</span>
                            <span className="agent-action-copy">
                                <strong>{action.title}</strong>
                                <span>{action.description}</span>
                            </span>
                            <span className="agent-action-arrow" aria-hidden="true">›</span>
                        </button>
                    ))}
                </div>

                {pendingAction && (
                    <div className="agent-action-confirm" role="region" aria-label={`Confirm ${pendingAction.title}`}>
                        <strong>{pendingAction.title}</strong>
                        <p>{pendingAction.impact}</p>
                        <div className="agent-action-confirm-context">
                            {pendingAction.confirmLabel || 'Selected context'}: {selectedNodes.length} {selectedNodes.length === 1 ? 'node' : 'nodes'}
                        </div>
                        {pendingAction.id === 'bubble-up' && (
                            <div className="agent-rollup-preview">
                                <div className="agent-rollup-preview-heading">
                                    <strong>Parent notes to rewrite</strong>
                                    <span>{rollupPreview.parents.filter(node => node.writeAllowed && !excludedRollupNodeIds.has(node.id)).length} of {rollupPreview.parents.length}</span>
                                </div>
                                {rollupPreview.parents.length ? (
                                    <div className="agent-rollup-node-list">
                                        {rollupPreview.parents.map(node => (
                                            <Form.Check
                                                key={node.id}
                                                id={`rollup-${node.id}`}
                                                type="checkbox"
                                                checked={node.writeAllowed && !excludedRollupNodeIds.has(node.id)}
                                                disabled={!node.writeAllowed}
                                                label={`${node.title}${node.writeAllowed ? '' : ' — connector-managed, read-only'}`}
                                                onChange={event => setExcludedRollupNodeIds(previous => {
                                                    const next = new Set(previous);
                                                    if (event.target.checked) next.delete(node.id);
                                                    else next.add(node.id);
                                                    return next;
                                                })}
                                            />
                                        ))}
                                    </div>
                                ) : <div className="agent-rollup-empty">The selected node has no children to roll up.</div>}
                                <small>{rollupPreview.leafCount} leaf {rollupPreview.leafCount === 1 ? 'node is' : 'nodes are'} used as unchanged source material.</small>
                            </div>
                        )}
                        <div className="agent-action-confirm-buttons">
                            <Button variant="outline-secondary" size="sm" onClick={() => setPendingAction(null)} disabled={queueMutation.isPending}>
                                Cancel
                            </Button>
                            <Button variant="primary" size="sm" onClick={handleConfirmAction} disabled={queueMutation.isPending || (pendingAction.id === 'bubble-up' && !rollupPreview.parents.some(node => node.writeAllowed && !excludedRollupNodeIds.has(node.id)))}>
                                {queueMutation.isPending ? 'Queuing…' : pendingAction.buttonLabel}
                            </Button>
                        </div>
                    </div>
                )}
            </div>

            <hr className="my-1" />

            <div className="agent-recent-jobs">
                <div className="d-flex justify-content-between align-items-center mb-2">
                    <h6 className="text-muted mb-0">
                        Recent jobs
                        <span className="ms-1" style={{ fontSize: '0.7rem', fontWeight: 400 }}>
                            (last 20)
                        </span>
                    </h6>
                    <Form.Select
                        size="sm"
                        className="w-auto py-0 text-muted"
                        value={statusFilter}
                        onChange={e => setStatusFilter(e.target.value)}
                        style={{ fontSize: '0.8rem' }}
                    >
                        <option value="">All Statuses</option>
                        <option value="pending">Pending</option>
                        <option value="processing">Processing</option>
                        <option value="completed">Completed</option>
                        <option value="failed">Failed</option>
                    </Form.Select>
                </div>

                <div className="pe-1">
                    {loadingTasks ? (
                        <div className="text-center text-muted small py-3">Loading tasks...</div>
                    ) : tasks.length === 0 ? (
                        <div className="text-center text-muted small py-3 fst-italic">No tasks found.</div>
                    ) : (
                        <div className="d-flex flex-column gap-2">
                            {tasks.map(task => (
                                <TaskCard key={task.id} task={task} vaultId={vaultId} />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
