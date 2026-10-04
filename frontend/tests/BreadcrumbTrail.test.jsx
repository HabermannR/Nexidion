import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, expect, test } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import BreadcrumbTrail from '../src/features/workspace/BreadcrumbTrail.jsx';

afterEach(cleanup);

function CurrentLocation() {
    return <output aria-label="Current route">{useLocation().pathname}</output>;
}

test('deep paths keep the current node visible and hidden ancestors navigable', async () => {
    const path = ['Vault', 'First ancestor', 'Second ancestor', 'Direct parent', 'Current node']
        .map((title, index) => ({ id: String(index), title, to: `/nodes/${index}` }));
    render(
        <MemoryRouter>
            <BreadcrumbTrail path={path} />
            <CurrentLocation />
        </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Vault' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Direct parent' })).toBeVisible();
    expect(screen.getByText('Current node')).toBeVisible();
    expect(screen.queryByRole('link', { name: 'Second ancestor' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Show hidden ancestors' }));
    fireEvent.click(await screen.findByRole('link', { name: 'Second ancestor' }));
    expect(screen.getByLabelText('Current route')).toHaveTextContent('/nodes/2');
});
