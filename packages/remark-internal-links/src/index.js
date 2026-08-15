import { syntax } from './syntax.js';
import { fromMarkdown } from './from-markdown.js';

export default function remarkInternalLinks() {

    const data = this.data();

    function add(field, value) {
        if (data[field]) {
            data[field].push(value);
        } else {
            data[field] = [value];
        }
    }
    add('micromarkExtensions', syntax());
    add('fromMarkdownExtensions', fromMarkdown());
}