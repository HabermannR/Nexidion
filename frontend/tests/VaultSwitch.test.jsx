import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, expect, test, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import AppShell from '../src/layouts/AppShell.jsx';
import { useWorkspaceStore } from '../src/features/workspace/workspaceStore.js';

vi.mock('../src/features/vaults/hooks/useVaultsQuery', () => ({
    useVaultsQuery: () => ({ data: [{ id: 1, name: 'First vault' }, { id: 2, name: 'Second vault' }] }),
}));
vi.mock('../src/features/auth/useUserQuery', () => ({ useUserQuery: () => ({ data: { username: 'Tester' } }) }));
vi.mock('../src/features/auth/useLogoutMutation.js', () => ({ useLogoutMutation: () => ({ mutate: vi.fn() }) }));
vi.mock('../src/features/print/PrintPreview.jsx', () => ({ default: () => null }));

afterEach(() => { cleanup(); useWorkspaceStore.getState().resetWorkspaceContext(); });

function Destination() {
    const { vaultId } = useParams();
    const selection = useWorkspaceStore(state => state.selectedNodeIds);
    return <output aria-label="Vault context">{vaultId}:{[...selection].join(',')}</output>;
}

test('switching vaults clears selection, editor, breadcrumbs and print data while retaining per-vault paths', async () => {
    useWorkspaceStore.setState({
        selectedNodeIds: new Set(['old-node']), collapsedNodes: new Set(['old-parent']),
        isEditingNode: true, breadcrumbPath: [{ id: 'old-node' }],
        printPreviewData: { nodes: ['old-node'] }, lastValidPaths: { 2: '/vaults/2/nodes/target' },
    });
    render(
        <MemoryRouter initialEntries={['/vaults/1/nodes/old-node']}>
            <Routes>
                <Route path="/vaults/:vaultId/nodes/:nodeId" element={<AppShell />}>
                    <Route index element={<Destination />} />
                </Route>
            </Routes>
        </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Switch Vault' }));
    fireEvent.click(await screen.findByRole('link', { name: 'Second vault' }));
    expect(screen.getByLabelText('Vault context')).toHaveTextContent('2:');
    const state = useWorkspaceStore.getState();
    expect(state.selectedNodeIds.size).toBe(0);
    expect(state.collapsedNodes.size).toBe(0);
    expect(state.isEditingNode).toBe(false);
    expect(state.breadcrumbPath).toEqual([]);
    expect(state.printPreviewData).toBeNull();
    expect(state.lastValidPaths[1]).toBe('/vaults/1/nodes/old-node');
    expect(state.lastValidPaths[2]).toBe('/vaults/2/nodes/target');
});
