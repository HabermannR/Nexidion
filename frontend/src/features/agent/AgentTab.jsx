// src/features/agent/AgentTab.jsx
import React, { useState, useMemo } from 'react';
import { useParams, NavLink } from 'react-router-dom';
import { Button, Form } from 'react-bootstrap';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useWorkspaceStore } from '../workspace/workspaceStore';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';
import apiClient from '../../api/apiClient';
import { useToast } from '../../components/ToastProvider';

// Import our new theme-compliant stylesheet
import './AgentTab.css';

// Operation accent colors mapped to generic custom properties (so they can be easily overridden)
const OPERATION_META = {
    create_node:             { label: 'Created node',  color: 'var(--agent-op-create, #2e7d5e)', icon: '✦' },
    patch_node:              { label: 'Patched node',  color: 'var(--primary-color, #405d83)', icon: '✎' },
    write_node:              { label: 'Wrote node',    color: 'var(--agent-op-write, #2e6b7d)', icon: '▤' },
    write_node_summary_only: { label: 'Summary only',  color: 'var(--agent-op-summary, #888888)', icon: '◎' },
    delete_node:             { label: 'Deleted node',  color: 'var(--agent-op-delete, #a03535)', icon: '✕' },
    move_node:               { label: 'Moved node',    color: 'var(--agent-op-move, #7a6020)', icon: '⇢' },
};

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
                    <span className="agent-op-id">
                        {shortId}
                    </span>
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

// ─── TaskDetail — fetched on expand ──────────────────────────────────────────

function TaskDetail({ taskId, vaultId }) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ['agentTask', taskId],
        queryFn: async () => {
            const res = await apiClient.get(`/api/tasks/${taskId}`);
            return res.data;
        },
        staleTime: 10_000,
    });

    if (isLoading) return (
        <div className="text-muted small py-2">Loading…</div>
    );
    if (isError || !data) return (
        <div className="text-danger small py-2">Failed to load detail.</div>
    );

    const operations = Array.isArray(data.operations) ? data.operations : [];

    return (
        <div className="agent-task-detail-container">

            {/* Input */}
            <div>
                <div className="agent-task-section-title">Input</div>
                <div className="agent-task-box is-input">
                    {data.instruction || <span className="text-muted">—</span>}
                </div>
            </div>

            {/* Output */}
            <div>
                <div className="agent-task-section-title">Output</div>
                <div className="agent-task-box">
                    {data.finish_summary
                        ? data.finish_summary
                        : <span className="text-muted fst-italic">No output yet</span>
                    }
                </div>
            </div>

            {/* Operations */}
            <div>
                <div className="agent-task-section-title">
                    Operations ({operations.length})
                </div>
                {operations.length === 0 ? (
                    <div className="text-muted small fst-italic">No write operations recorded.</div>
                ) : (
                    <div className="d-flex flex-column gap-1">
                        {operations.map((op, i) => <OperationRow key={i} op={op} vaultId={vaultId} />)}
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
    const preview = task.preview_text || '';

    return (
        <div className={`agent-task-card ${expanded ? 'expanded' : ''}`}>
            <div
                className="agent-task-card-header"
                onClick={() => setExpanded(e => !e)}
            >
                <div className="d-flex gap-2 align-items-start">
                    <div className={`agent-task-card-preview ${!expanded ? 'is-collapsed' : ''}`}>
                        {preview}
                    </div>
                    <StatusBadge status={task.status} />
                </div>

                <div className="agent-task-card-meta">
                    <span className="agent-task-card-id">
                        {String(task.id).substring(0, 8)}
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
            </div>

            {expanded && (
                <div className="agent-task-card-body">
                    <TaskDetail taskId={task.id} vaultId={vaultId} />
                </div>
            )}
        </div>
    );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AgentTab() {
    const {vaultId} = useParams();
    const queryClient = useQueryClient();
    const toast = useToast();
    const [instruction, setInstruction] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [statusFilter, setStatusFilter] = useState('');

    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const {data: queryData} = useVaultTreeQuery(vaultId);
    const allNodesFlat = useMemo(() => queryData?.allNodesFlat || [], [queryData]);

    const selectedNodes = useMemo(() => {
        if (allNodesFlat.length === 0 || selectedNodeIds.size === 0) return [];
        const nodeMap = new Map(allNodesFlat.map(n => [n.id, n]));
        return Array.from(selectedNodeIds)
            .map(id => ({id, title: nodeMap.get(id)?.title || id}))
            .sort((a, b) => a.title.localeCompare(b.title));
    }, [selectedNodeIds, allNodesFlat]);

    const {data: tasks = [], isLoading: loadingTasks} = useQuery({
        queryKey: ['agentTasks', vaultId, statusFilter],
        queryFn: async () => {
            const params = {vault_id: vaultId, limit: 20};
            if (statusFilter) params.status = statusFilter;
            const res = await apiClient.get('/api/tasks', {params});
            return Array.isArray(res.data) ? res.data : (res.data.tasks || []);
        },
        refetchInterval: 5000,
    });

    const handleSend = async () => {
        if (!instruction.trim() || isSending) return;
        setIsSending(true);
        try {
            await apiClient.post('/api/tasks', {
                vault_id: parseInt(vaultId),
                instruction: instruction.trim(),
                context_node_ids: Array.from(selectedNodeIds),
            });
            setInstruction('');
            toast.success('Task added to queue');
            queryClient.invalidateQueries({queryKey: ['agentTasks', vaultId]});
        } catch (err) {
            const msg = err.response?.data?.error;
            if (err.response?.status === 403) {
                toast.error(msg || 'You don\'t have permission to submit tasks in this vault.');
            } else if (err.response?.status === 429) {
                toast.error('Too many tasks — please wait before submitting again.');
            } else {
                toast.error(msg || 'Failed to queue task — check your connection.');
            }
        } finally {
            setIsSending(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSend();
    };

    return (
        <div className="p-3 d-flex flex-column gap-3 h-100">
            <div className="flex-shrink-0">
                <h6 className="text-muted mb-2">Queue Agent Task</h6>

                <div className="mb-2">
                    <small className="text-muted fw-bold d-block mb-1">
                        Context nodes ({selectedNodes.length})
                    </small>
                    {selectedNodes.length === 0 ? (
                        <small className="text-muted fst-italic">
                            No nodes selected — use the tree to select context nodes
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

                <textarea
                    className="form-control form-control-sm font-monospace"
                    rows={4}
                    placeholder={"Instruction for the agent…\n\n(Ctrl+Enter to send)"}
                    value={instruction}
                    onChange={e => setInstruction(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={status === 'sending'}
                    style={{resize: 'vertical', fontSize: '0.82rem'}}
                />

                <div className="d-grid mt-3">
                    <Button
                        variant="primary"
                        size="sm"
                        onClick={handleSend}
                        disabled={!instruction.trim() || isSending}
                    >
                        {isSending ? 'Queuing…' : 'Queue Task ↗'}
                    </Button>
                </div>
            </div>

            <hr className="my-1"/>

            <div className="flex-grow-1 d-flex flex-column" style={{minHeight: 0}}>
                <div className="d-flex justify-content-between align-items-center mb-2">
                    <h6 className="text-muted mb-0">
                        Tasks
                        <span className="ms-1" style={{fontSize: '0.7rem', fontWeight: 400}}>
                            (last 20)
                        </span>
                    </h6>
                    <Form.Select
                        size="sm"
                        className="w-auto py-0 text-muted"
                        value={statusFilter}
                        onChange={e => setStatusFilter(e.target.value)}
                        style={{fontSize: '0.8rem'}}
                    >
                        <option value="">All Statuses</option>
                        <option value="pending">Pending</option>
                        <option value="processing">Processing</option>
                        <option value="completed">Completed</option>
                        <option value="failed">Failed</option>
                    </Form.Select>
                </div>

                <div className="flex-grow-1 overflow-auto pe-1 custom-scrollbar">
                    {loadingTasks ? (
                        <div className="text-center text-muted small py-3">Loading tasks...</div>
                    ) : tasks.length === 0 ? (
                        <div className="text-center text-muted small py-3 fst-italic">No tasks found.</div>
                    ) : (
                        <div className="d-flex flex-column gap-2">
                            {tasks.map(task => (
                                <TaskCard key={task.id} task={task} vaultId={vaultId}/>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}