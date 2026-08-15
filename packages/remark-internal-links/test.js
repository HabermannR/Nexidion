// test.js

import { unified } from 'unified'
import remarkParse from 'remark-parse'
import assert from 'node:assert/strict'
import remarkInternalLinksPlugin from './src/index.js'

const markdownInput = `
# Document with internal links

A strong link: [[Project notes|a1b2c3d4-e5f6-4a3b-8c2d-1e9f0a2b1c3d]]

A weak link: [[Node title]]

A weak link with an alias: [[Actual title|Custom text]]

A hostile display value: [[<img src=x>|a1b2c3d4-e5f6-4a3b-8c2d-1e9f0a2b1c3d]]

A malformed link remains text: [[not closed

A normal sentence without a link.
`;

const processor = unified()
    .use(remarkParse)
    .use(remarkInternalLinksPlugin);

const ast = processor.parse(markdownInput);
const links = ast.children.flatMap(node => node.children || [])
    .filter(node => node.type === 'html');

assert.equal(links.length, 4);
assert.match(links[0].value, /class="internal-link strong-link"/);
assert.match(links[1].value, /data-target="Node%20title"/);
assert.match(links[2].value, /data-display-text="Custom%20text"/);
assert.match(links[3].value, /&lt;img src=x&gt;/);
assert.doesNotMatch(links[3].value, /><img/);

console.log('remark-internal-links: assertions passed');
