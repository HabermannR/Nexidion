import React from 'react';
import { Badge, Dropdown } from 'react-bootstrap';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import apiClient from '../../api/apiClient.js';
import { useToast } from '../../components/ToastProvider.jsx';

const PRESETS = [
    { id: 'normal', label: 'Normal', ai_read: 'allow', ai_write_locked: false, human_write_locked: false },
    { id: 'ai-write', label: 'AI write-locked', ai_read: 'allow', ai_write_locked: true, human_write_locked: false },
    { id: 'human-write', label: 'Write-locked', ai_read: 'allow', ai_write_locked: true, human_write_locked: true },
    { id: 'quarantine', label: 'Quarantine', ai_read: 'explicit_only', ai_write_locked: true, human_write_locked: false },
    { id: 'ai-invisible', label: 'AI invisible', ai_read: 'deny', ai_write_locked: true, human_write_locked: false },
];

function labelFor(policy) {
    if (policy?.ai_read === 'deny') return 'AI invisible';
    if (policy?.ai_read === 'explicit_only') return 'Quarantine';
    if (policy?.human_write_locked) return 'Write-locked';
    if (policy?.ai_write_locked) return 'AI write-locked';
    return 'Normal';
}

export default function AccessPolicyDropdown({ currentVersion, vaultId, nodeId }) {
    const queryClient = useQueryClient();
    const toast = useToast();
    const local = currentVersion?.access_policy || {};
    const effective = currentVersion?.effective_access_policy || local;
    const label = labelFor(effective);
    const restricted = label !== 'Normal';

    const mutation = useMutation({
        mutationFn: (preset) => apiClient.patch(
            `/api/vaults/${vaultId}/nodes/${nodeId}/access-policy`,
            { ...preset, note: local.note || null },
        ),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['nodeContent', vaultId, nodeId] });
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            toast.success('Node access policy updated.');
        },
        onError: (error) => toast.error(
            error.response?.data?.error || error.message || 'Could not update node access policy.'
        ),
    });

    return (
        <Dropdown>
            <Dropdown.Toggle
                variant="link"
                size="sm"
                className="access-policy-toggle p-0 border-0 bg-transparent shadow-none text-decoration-none"
                title={`${label}${effective?.inherited ? ' (inherited)' : ''}`}
            >
                <i className={`bx ${effective?.ai_read === 'deny' ? 'bxs-no-entry' : 'bxs-shield'} me-1`} />
                <Badge bg={restricted ? 'dark' : 'secondary'}>{label}</Badge>
            </Dropdown.Toggle>
            <Dropdown.Menu align="end">
                <Dropdown.Header>Node access policy</Dropdown.Header>
                {effective?.inherited && (
                    <Dropdown.ItemText className="small text-warning">
                        Ancestor restrictions remain effective.
                    </Dropdown.ItemText>
                )}
                {PRESETS.map(({ id, label: presetLabel, ...policy }) => (
                    <Dropdown.Item
                        key={id}
                        disabled={mutation.isPending}
                        onClick={() => mutation.mutate(policy)}
                    >
                        {presetLabel}
                    </Dropdown.Item>
                ))}
            </Dropdown.Menu>
        </Dropdown>
    );
}
