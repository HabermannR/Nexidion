// src/utils/textUtils.js
import React from 'react';

/**
 * Rendert Text mit internen Links im Format [[LinkTarget|DisplayText]]
 * @param {React.ReactNode} children - Die Kinder-Elemente
 * @param {Function} onLinkClick - Callback-Funktion für Link-Klicks
 * @returns {React.ReactNode} - Die verarbeiteten Kinder-Elemente
 */
export const renderTextWithLinks = (children, onLinkClick) => {
    return React.Children.map(children, child => {
        if (typeof child === 'string') {
            const linkRegex = /\[\[\s*([^|\]\s][^|\]]*?)\s*(?:\|\s*(.+?)\s*)?\]\]/g;
            const parts = [];
            let lastIndex = 0;
            const matches = [...child.matchAll(linkRegex)];
            
            if (matches.length === 0) { 
                return child; 
            }
            
            matches.forEach((match, index) => {
                const [fullMatch, target, displayText] = match;
                const matchIndex = match.index;
                
                if (matchIndex > lastIndex) {
                    parts.push(child.substring(lastIndex, matchIndex));
                }
                
                parts.push(
                    <span 
                        key={`${target}-${index}`} 
                        onClick={() => onLinkClick && onLinkClick(target)} 
                        className="internal-link" 
                        role="button" 
                        tabIndex={0}
                    >
                        {displayText || target}
                    </span>
                );
                
                lastIndex = matchIndex + fullMatch.length;
            });
            
            if (lastIndex < child.length) {
                parts.push(child.substring(lastIndex));
            }
            
            return parts;
        }
        
        if (React.isValidElement(child) && child.props.children) {
            return React.cloneElement(child, { 
                children: renderTextWithLinks(child.props.children, onLinkClick) 
            });
        }
        
        return child;
    });
};