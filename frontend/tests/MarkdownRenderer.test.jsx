import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, test } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import MarkdownRenderer from '../src/features/nodes/MarkdownRenderer.jsx';

afterEach(cleanup);

function renderMarkdown(content) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={['/vaults/2/nodes/current']}>
                <Routes>
                    <Route path="/vaults/:vaultId/nodes/:nodeId" element={
                        <MarkdownRenderer content={content} />
                    } />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>,
    );
}

describe('MarkdownRenderer internal links', () => {
    test('renders a title-based wiki link as a clickable anchor', () => {
        renderMarkdown('Open [[Target title]] now.');

        const link = screen.getByRole('link', { name: 'Target title' });
        expect(link).toHaveClass('internal-link', 'weak-link');
    });

    test('renders a UUID wiki link as a clickable anchor', () => {
        renderMarkdown(
            'Open [[Strong label|27cc5022-0370-4543-9cdd-43fafb8d1282]] now.',
        );

        const link = screen.getByRole('link', { name: 'Strong label' });
        expect(link).toHaveClass('internal-link', 'strong-link');
    });

    test('renders hostile link text literally instead of creating HTML', () => {
        renderMarkdown(
            'Open [[<img src=x>|27cc5022-0370-4543-9cdd-43fafb8d1282]] now.',
        );

        expect(screen.getByRole('link', { name: '<img src=x>' })).toBeInTheDocument();
        expect(document.querySelector('.markdown-body img')).toBeNull();
    });
});
