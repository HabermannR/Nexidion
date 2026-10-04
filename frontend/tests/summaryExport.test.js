import { expect, test } from 'vitest';
import { formatSummaryTree } from '../src/lib/summaryExport.js';

test('summary exports retain titles, UUIDs and hierarchy with a visible empty-summary marker', () => {
    const rootId = '27cc5022-0370-4543-9cdd-43fafb8d1282';
    const childId = 'b96a7ecf-cbc5-4a5e-afbd-07f6ee0b74a2';
    const text = formatSummaryTree([{ id: rootId, title: 'Root', ai_summary: '- First\r\n- Second',
        children: [{ id: childId, title: 'Child', ai_summary: '' }],
    }]);
    expect(text).toContain(`- Root (${rootId})\n`);
    expect(text).toContain(`  - Child (${childId})\n`);
    expect(text).toContain('  - First\n  - Second\n');
    expect(text).toContain('    [No AI summary]\n');
    expect(text).not.toContain('\r');
});
