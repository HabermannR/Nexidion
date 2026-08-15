import { expect, test } from 'vitest';

import { sanitize } from 'hast-util-sanitize';

import { markdownSanitizeSchema } from '../src/features/nodes/markdownSanitizeSchema.js';

test('preserves strong and weak internal-link metadata', () => {
    const tree = {
        type: 'root',
        children: [
            {
                type: 'element',
                tagName: 'span',
                properties: {
                    className: ['internal-link', 'strong-link'],
                    dataUuid: '27cc5022-0370-4543-9cdd-43fafb8d1282',
                    dataDisplayText: 'Strong link',
                },
                children: [{ type: 'text', value: 'Strong link' }],
            },
            {
                type: 'element',
                tagName: 'span',
                properties: {
                    className: ['internal-link', 'weak-link'],
                    dataTarget: 'Target title',
                    dataDisplayText: 'Weak link',
                },
                children: [{ type: 'text', value: 'Weak link' }],
            },
        ],
    };

    const result = sanitize(tree, markdownSanitizeSchema);

    expect(result.children[0].properties.dataUuid)
        .toBe('27cc5022-0370-4543-9cdd-43fafb8d1282');
    expect(result.children[0].properties.dataDisplayText).toBe('Strong link');
    expect(result.children[1].properties.dataTarget).toBe('Target title');
    expect(result.children[1].properties.dataDisplayText).toBe('Weak link');
});
