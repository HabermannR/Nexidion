// src/features/agent/AgentTab.jsx
import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Button, Alert, Form } from 'react-bootstrap';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useWorkspaceStore } from '../workspace/workspaceStore';
import { useVaultTreeQuery } from '../nodes/hooks/useVaultTreeQuery';
import apiClient from '../../api/apiClient';

export default function AgentTab() {
    const { vaultId } = useParams();
    const queryClient = useQueryClient();
    const[instruction, setInstruction] = useState('');
    const [status, setStatus] = useState('idle'); // 'idle' | 'sending' | 'sent' | 'error'
    const [statusFilter, setStatusFilter] = useState('');
	const [expandedTasks, setExpandedTasks] = useState(new Set());

    const selectedNodeIds = useWorkspaceStore(state => state.selectedNodeIds);
    const { data: queryData } = useVaultTreeQuery(vaultId);
    const allNodesFlat = useMemo(() => queryData?.allNodesFlat || [], [queryData]);

    const selectedNodes = useMemo(() => {
        if (allNodesFlat.length === 0 || selectedNodeIds.size === 0) return[];
        const nodeMap = new Map(allNodesFlat.map(n => [n.id, n]));
        return Array.from(selectedNodeIds)
            .map(id => ({ id, title: nodeMap.get(id)?.title || id }))
            .sort((a, b) => a.title.localeCompare(b.title));
    }, [selectedNodeIds, allNodesFlat]);

    const { data: tasks = [], isLoading: loadingTasks } = useQuery({
        queryKey:['agentTasks', vaultId, statusFilter],
        queryFn: async () => {
            const params = { vault_id: vaultId };
            if (statusFilter) params.status = statusFilter;
            const res = await apiClient.get('/api/tasks', { params });
            return Array.isArray(res.data) ? res.data : (res.data.tasks ||[]);
        },
        refetchInterval: 5000,
    });

    const handleSend = async () => {
        if (!instruction.trim() || status === 'sending') return;
        setStatus('sending');
        try {
            await apiClient.post('/api/tasks', {
                vault_id: parseInt(vaultId),
                instruction: instruction.trim(),
                context_node_ids: Array.from(selectedNodeIds),
            });
            setInstruction('');
            setStatus('sent');
            queryClient.invalidateQueries({ queryKey: ['agentTasks', vaultId] });
            setTimeout(() => setStatus('idle'), 3000);
        } catch {
            setStatus('error');
            setTimeout(() => setStatus('idle'), 4000);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            handleSend();
        }
    };
	
	const toggleTaskExpansion = (taskId) => {
        setExpandedTasks(prev => {
            const next = new Set(prev);
            if (next.has(taskId)) next.delete(taskId);
            else next.add(taskId);
            return next;
        });
    };

    return (
        <div className="p-3 d-flex flex-column gap-3 h-100">
            <div className="flex-shrink-0">
                <h6 className="text-muted mb-2">Queue Agent Task</h6>

                {/* Context nodes display */}
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

                {/* Instruction textarea */}
                <textarea
                    className="form-control form-control-sm font-monospace"
                    rows={4}
                    placeholder={"Instruction for the agent…\n\n(Ctrl+Enter to send)"}
                    value={instruction}
                    onChange={e => setInstruction(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={status === 'sending'}
                    style={{ resize: 'vertical', fontSize: '0.82rem' }}
                />

                <div className="d-grid mt-3">
                    <Button
                        variant="primary"
                        size="sm"
                        onClick={handleSend}
                        disabled={!instruction.trim() || status === 'sending'}
                    >
                        {status === 'sending' ? 'Queuing…' : 'Queue Task ↗'}
                    </Button>
                </div>

                {status === 'sent' && (
                    <Alert variant="success" className="py-2 px-3 mt-2 mb-0 small">
                        ✓ Task added to queue
                    </Alert>
                )}
                {status === 'error' && (
                    <Alert variant="danger" className="py-2 px-3 mt-2 mb-0 small">
                        ✗ Failed to queue task — check connection
                    </Alert>
                )}
            </div>

            <hr className="my-1" />

            <div className="flex-grow-1 d-flex flex-column" style={{ minHeight: 0 }}>
                <div className="d-flex justify-content-between align-items-center mb-2">
                    <h6 className="text-muted mb-0">Tasks</h6>
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
                
                <div className="flex-grow-1 overflow-auto pe-1 custom-scrollbar">
                    {loadingTasks ? (
                        <div className="text-center text-muted small py-3">Loading tasks...</div>
                    ) : tasks.length === 0 ? (
                        <div className="text-center text-muted small py-3 fst-italic">No tasks found.</div>
                    ) : (
                        <div className="d-flex flex-column gap-2">
                            {tasks.map(task => {
                                // Prüfen ob Text lang genug ist, um überhaupt zu klappen
                                const isLong = task.instruction?.length > 90;
                                const isExpanded = expandedTasks.has(task.id);

                                return (
                                <div key={task.id} className="card border shadow-sm small">
                                    <div className="card-body p-2 d-flex flex-column gap-2">
                                        
                                        <div className="d-flex justify-content-between align-items-start gap-2">
                                            {/* TEXT: Line-Clamp beschneidet auf 2 Zeilen mit '...' */}
                                            <div 
                                                className="text-break text-wrap font-monospace" 
                                                style={{ 
                                                    fontSize: '0.75rem', 
                                                    flex: 1, 
                                                    minWidth: 0,
                                                    display: (!isLong || isExpanded) ? 'block' : '-webkit-box',
                                                    WebkitLineClamp: (!isLong || isExpanded) ? 'unset' : 2,
                                                    WebkitBoxOrient: 'vertical',
                                                    overflow: 'hidden',
                                                    cursor: isLong ? 'pointer' : 'default'
                                                }}
                                                onClick={() => isLong && toggleTaskExpansion(task.id)}
                                                title={isLong && !isExpanded ? "Klicken zum Ausklappen" : ""}
                                            >
                                                {task.instruction}
                                            </div>
                                            
                                            {/* BADGE */}
                                            <span className={`badge bg-${
                                                task.status === 'completed' ? 'success' : 
                                                task.status === 'failed' ? 'danger' : 
                                                task.status === 'processing' ? 'warning text-dark' : 'secondary'
                                            } py-1 px-2 flex-shrink-0 mt-1`} style={{fontSize: '0.65rem'}}>
                                                {task.status}
                                            </span>
                                        </div>

                                        {/* UNTERER BEREICH: ID, "Mehr"-Link und Datum */}
                                        <div className="text-muted d-flex justify-content-between align-items-center" style={{fontSize: '0.65rem'}}>
                                            <div className="d-flex gap-2 align-items-center">
                                                <span>ID: {String(task.id).substring(0, 8)}</span>
                                                
                                                {/* Zeige "Mehr/Weniger" nur bei langen Texten */}
                                                {isLong && (
                                                    <span 
                                                        className="text-primary"
                                                        style={{ cursor: 'pointer', textDecoration: 'underline' }}
                                                        onClick={() => toggleTaskExpansion(task.id)}
                                                    >
                                                        {isExpanded ? 'Weniger' : 'Mehr'}
                                                    </span>
                                                )}
                                            </div>
                                            <span>
                                                {task.created_at ? new Date(task.created_at).toLocaleString() : ''}
                                            </span>
                                        </div>
                                        
                                    </div>
                                </div>
                            )})}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}