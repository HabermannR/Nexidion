import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, expect, test, vi } from 'vitest';
import apiClient from '../src/api/apiClient';
import SecureImage from '../src/components/SecureImage.jsx';

vi.mock('../src/api/apiClient', () => ({ default: { get: vi.fn() } }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

test('returning to a vault creates a fresh URL from the cached image without fetching again', async () => {
    let counter = 0;
    const createUrl = vi.fn(() => `blob:image-${++counter}`);
    const revokeUrl = vi.fn();
    vi.stubGlobal('URL', { createObjectURL: createUrl, revokeObjectURL: revokeUrl });
    apiClient.get.mockResolvedValue({ data: new Blob(['image'], { type: 'image/png' }) });
    const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const asset = '/api/vaults/1/assets/27cc5022-0370-4543-9cdd-43fafb8d1282';
    const element = (
        <QueryClientProvider client={cache}><SecureImage src={asset} alt="Vault image" /></QueryClientProvider>
    );
    const first = render(element);
    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:image-1'));
    first.unmount();
    expect(revokeUrl).toHaveBeenCalledWith('blob:image-1');
    const second = render(element);
    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:image-2'));
    expect(apiClient.get).toHaveBeenCalledTimes(1);
    second.unmount();
    expect(revokeUrl).toHaveBeenCalledWith('blob:image-2');
    cache.clear();
});
