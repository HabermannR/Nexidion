// Stable Markdown: title + UUID, followed by indented summary and descendants.
export function formatSummaryTree(nodes, depth = 0) {
    const indent = '  '.repeat(depth);
    const summaryIndent = '  '.repeat(depth + 1);
    return nodes.map(node => {
        const title = (node.title || 'Untitled node').replace(/[\r\n]+/g, ' ');
        const summary = node.ai_summary?.trim() || '[No AI summary]';
        return `${indent}- ${title} (${node.id})\n`
            + `${summaryIndent}${summary.replace(/\r?\n/g, `\n${summaryIndent}`)}\n`
            + formatSummaryTree(node.children || [], depth + 1);
    }).join('');
}
