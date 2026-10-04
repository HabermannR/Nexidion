import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, expect, test, vi } from 'vitest';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import apiClient from '../src/api/apiClient.js';
import { ToastProvider } from '../src/components/ToastProvider.jsx';
import NodeContent from '../src/features/nodes/NodeContent.jsx';
import BreadcrumbTrail from '../src/features/workspace/BreadcrumbTrail.jsx';
import { useWorkspaceStore } from '../src/features/workspace/workspaceStore.js';

vi.mock('../src/api/apiClient.js', () => ({ default: { get: vi.fn() } }));
vi.mock('../src/features/nodes/ContentHeader.jsx', () => ({ default: () => null }));
vi.mock('../src/features/nodes/NodeEditor.jsx', () => ({ default: () => null }));
vi.mock('../src/components/DiffViewer.jsx', () => ({ default: () => null }));

afterEach(() => {
    cleanup();
    useWorkspaceStore.getState().resetWorkspaceContext();
    vi.clearAllMocks();
});

const documentId = 'd3f5b4aa-6435-444f-9942-113f6f30bb2d';
const ingestId = 'bb004a6c-7bf0-4a28-ac99-3e3aad14d516';
// Real tree responses omit vault_id on every node.
const tree = [{ id: 'root', title: 'Nexidion', children: [
    { id: 'architecture', title: 'Architecture', children: [
        { id: 'api', title: 'API', children: [
            { id: ingestId, title: 'ingest', children: [
                { id: documentId, title: 'Resolved: PDF curation', children: [] },
            ] },
        ] },
    ] },
] }];

function Workspace() {
    const path = useWorkspaceStore(state => state.breadcrumbPath);
    const location = useLocation();
    return <>
        <BreadcrumbTrail path={path} />
        <NodeContent />
        <output aria-label="Current route">{location.pathname}</output>
        <Link to={`/vaults/20/nodes/${documentId}`}>Switch to vault 20</Link>
    </>;
}

function renderWorkspace() {
    apiClient.get.mockImplementation(async url => {
        if (url.endsWith('/nodes/')) return { data: tree, status: 200, headers: {} };
        if (url.endsWith('/versions')) return { data: [] };
        return { data: { id: url.split('/').pop(), title: 'Document', content: 'Node content',
            version: 1, current_version: 1 } };
    });
    const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
        <QueryClientProvider client={cache}>
            <ToastProvider>
                <MemoryRouter initialEntries={[`/vaults/10/nodes/${documentId}`]}>
                    <Routes>
                        <Route path="/vaults/:vaultId/nodes/:nodeId" element={<Workspace />} />
                    </Routes>
                </MemoryRouter>
            </ToastProvider>
        </QueryClientProvider>,
    );
    return cache;
}

test('clicking ingest uses the active vault even when tree nodes have no vault_id', async () => {
    const cache = renderWorkspace();
    const link = await screen.findByRole('link', { name: 'ingest' });
    expect(link).toHaveAttribute('href', `/vaults/10/nodes/${ingestId}`);
    fireEvent.click(link);
    expect(screen.getByLabelText('Current route')).toHaveTextContent(`/vaults/10/nodes/${ingestId}`);
    await waitFor(() => expect(apiClient.get).toHaveBeenCalledWith(
        `/api/vaults/10/nodes/${ingestId}`, { params: {} },
    ));
    cache.clear();
});

test('hidden ancestor links also use the active vault after switching vaults', async () => {
    const cache = renderWorkspace();
    await screen.findByRole('link', { name: 'ingest' });
    fireEvent.click(screen.getByRole('link', { name: 'Switch to vault 20' }));
    await waitFor(() => expect(screen.getByRole('link', { name: 'ingest' }))
        .toHaveAttribute('href', `/vaults/20/nodes/${ingestId}`));
    fireEvent.click(screen.getByRole('button', { name: 'Show hidden ancestors' }));
    const ancestor = await screen.findByRole('link', { name: 'API' });
    expect(ancestor).toHaveAttribute('href', '/vaults/20/nodes/api');
    fireEvent.click(ancestor);
    expect(screen.getByLabelText('Current route')).toHaveTextContent('/vaults/20/nodes/api');
    cache.clear();
});
