import React from 'react';
import { useInternalLinkNavigation } from './hooks/useInternalLinkNavigation'; // Pfad anpassen!

/**
 * @param {string} target - Das Link-Ziel (Titel oder UUID).
 * @param {React.ReactNode} children - Der Inhalt des Links, von ReactMarkdown gerendert.
 */
// Wir nehmen wieder `displayText` anstatt `children`
export default function InternalLink({ target, displayText }) {
    const { navigateToTitle } = useInternalLinkNavigation();

    const handleClick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        navigateToTitle(target);
    };

    // Es ist jetzt ein `a`-Tag, der wie ein Link aussieht und funktioniert,
    // aber aus einem `span`-Tag im Markdown "geboren" wurde.
    return (
        <a href="#" onClick={handleClick} className="internal-link">
            {displayText}
        </a>
    );
}