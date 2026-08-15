const uuidRegex = /^[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}$/i;

function escapeHtmlText(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
}

export function fromMarkdown() {
    let node;
    let dataBuffer;

    function top(stack) {
        return stack[stack.length - 1];
    }

    function enterInternalLink(token) {
        dataBuffer = {};
        this.enter({ type: 'internalLink' }, token);
        node = top(this.stack);
    }

    function exitInternalLinkTarget(token) {
        dataBuffer.target = this.sliceSerialize(token);
    }

    function exitInternalLinkAlias(token) {
        dataBuffer.alias = this.sliceSerialize(token);
    }

    function exitInternalLink(token) {
        this.exit(token);
        const { target, alias } = dataBuffer;

        let displayText = alias || target;
        let finalTarget = target;
        let isStrong = false;

        if (alias && uuidRegex.test(alias)) {
            isStrong = true;
            finalTarget = alias;
            displayText = target;
        }

        node.type = 'html';

        // Preserve strong/weak link classes for the React renderer.
        const baseClass = "internal-link";
        const typeClass = isStrong ? "strong-link" : "weak-link";
        const safeDisplayText = escapeHtmlText(displayText);

        if (isStrong) {
            node.value = `<span class="${baseClass} ${typeClass}" data-uuid="${finalTarget}" data-display-text="${encodeURIComponent(displayText)}">${safeDisplayText}</span>`;
        } else {
            node.value = `<span class="${baseClass} ${typeClass}" data-target="${encodeURIComponent(finalTarget)}" data-display-text="${encodeURIComponent(displayText)}">${safeDisplayText}</span>`;
        }
    }

    return {
        enter: { internalLink: enterInternalLink },
        exit: {
            internalLinkTarget: exitInternalLinkTarget,
            internalLinkAlias: exitInternalLinkAlias,
            internalLink: exitInternalLink
        }
    };
}
