import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Form } from 'react-bootstrap';
import { useParams } from 'react-router-dom';
import { useNodeSearchQuery } from './hooks/useNodeSearchQuery';
import './NodeEditor.css';

// Hilfsfunktion zum Prüfen auf UUID-Format
const isUuid = (str) => {
    if (typeof str !== 'string') return false;
    const uuidRegex = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
    return uuidRegex.test(str);
};

// Die Positionsberechnungs-Funktion (unverändert)
const getCaretCoordinates = (element, position) => {
    const { selectionStart, scrollTop, scrollLeft } = element;
    const pos = position !== undefined ? position : selectionStart;
    const rect = element.getBoundingClientRect();
    const div = document.createElement('div');
    document.body.appendChild(div);
    const style = div.style;
    const computed = window.getComputedStyle(element);
    style.position = 'absolute';
    style.visibility = 'hidden';
    style.top = `${rect.top}px`;
    style.left = `${rect.left}px`;
    style.width = `${element.clientWidth}px`;
    style.height = 'auto';
    style.whiteSpace = 'pre-wrap';
    style.wordWrap = 'break-word';
    ['padding', 'fontFamily', 'fontSize', 'fontStyle', 'fontWeight', 'letterSpacing', 'lineHeight', 'textIndent', 'textRendering', 'textTransform', 'border'].forEach(prop => {
        style[prop] = computed[prop];
    });
    div.textContent = element.value.substring(0, pos);
    const span = document.createElement('span');
    span.textContent = element.value.substring(pos) || '.';
    div.appendChild(span);
    const coordinates = {
        top: rect.top + span.offsetTop - scrollTop,
        left: rect.left + span.offsetLeft - scrollLeft,
        height: parseInt(computed.lineHeight)
    };
    document.body.removeChild(div);
    if (isNaN(coordinates.top) || isNaN(coordinates.left)) return null;
    return coordinates;
};

export default function NodeEditor({ content, onContentChange }) {
    const { vaultId } = useParams();
    const textareaRef = useRef(null);
    const dropdownRef = useRef(null);
    const [cursorPosition, setCursorPosition] = useState(null);
    const [showAutocomplete, setShowAutocomplete] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, height: 0 });
    const [activeWeakLink, setActiveWeakLink] = useState(null);

    const {
        data: searchResults = [],
        isLoading
    } = useNodeSearchQuery(vaultId, searchTerm);

    useEffect(() => {
        if (textareaRef.current && cursorPosition !== null) {
            textareaRef.current.focus();
            textareaRef.current.setSelectionRange(cursorPosition, cursorPosition);
            setCursorPosition(null);
        }
    }, [cursorPosition]);

    useEffect(() => {
        if (showAutocomplete && dropdownRef.current && searchResults.length > 0) {
            const selectedItem = dropdownRef.current.querySelector('.autocomplete-item.selected');
            if (selectedItem) selectedItem.scrollIntoView({ block: 'nearest' });
        }
    }, [selectedIndex, searchResults, showAutocomplete]);

    useEffect(() => { setSelectedIndex(0); }, [searchResults]);

    const startRepairMode = useCallback(() => {
        if (!activeWeakLink || !textareaRef.current) return;
        setSearchTerm(activeWeakLink.searchTerm);
        setShowAutocomplete(true);
        const pos = getCaretCoordinates(textareaRef.current, activeWeakLink.range.end);
        if (pos) setDropdownPosition(pos);
    }, [activeWeakLink]);

    // --- NEU: Dieser Hook startet den Reparaturmodus automatisch ---
    useEffect(() => {
        // Wenn ein schwacher Link durch einen Klick identifiziert wurde...
        if (activeWeakLink && !showAutocomplete) {
            // ...starte den Reparaturmodus sofort.
            startRepairMode();
        }
    }, [activeWeakLink, showAutocomplete, startRepairMode]);


    const checkForActiveLink = (text, cursorIdx) => {
        const weakLinkRegex = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;
        let match;
        while ((match = weakLinkRegex.exec(text)) !== null) {
            const [fullMatch, part1, part2] = match;
            const start = match.index;
            const end = start + fullMatch.length;
            if (isUuid(part2)) continue;
            if (cursorIdx > start && cursorIdx < end) {
                setActiveWeakLink({
                    searchTerm: part1,
                    displayAlias: part2 || part1,
                    range: { start, end }
                });
                return;
            }
        }
        setActiveWeakLink(null);
    };

    const handleSelectionChange = (e) => {
        if (showAutocomplete) {
            setActiveWeakLink(null);
            return;
        }
        checkForActiveLink(e.target.value, e.target.selectionStart);
    };

    const handleContentChange = (e) => {
        const newContent = e.target.value;
        onContentChange(newContent);
        const textBeforeCursor = newContent.substring(0, e.target.selectionStart);
        const match = textBeforeCursor.match(/\[\[([^\]|]*)$/);
        if (match) {
            setActiveWeakLink(null);
            setSearchTerm(match[1]);
            setShowAutocomplete(true);
            if (textareaRef.current) {
                const pos = getCaretCoordinates(textareaRef.current);
                if (pos) setDropdownPosition(pos);
            }
        } else {
            setShowAutocomplete(false);
        }
    };

    const selectResult = (result) => {
        const currentContent = textareaRef.current.value;
        let strongLink;
        let newContent;
        let newCursorPos;
        if (activeWeakLink) {
            strongLink = `[[${activeWeakLink.displayAlias}|${result.id}]]`;
            const { start, end } = activeWeakLink.range;
            newContent = currentContent.substring(0, start) + strongLink + currentContent.substring(end);
            newCursorPos = start + strongLink.length;
        } else {
            strongLink = `[[${result.title}|${result.id}]]`;
            const cursorIdx = textareaRef.current.selectionStart;
            const textBeforeCursor = currentContent.substring(0, cursorIdx);
            const linkStartIndex = textBeforeCursor.lastIndexOf('[[');
            newContent = currentContent.substring(0, linkStartIndex) + strongLink + currentContent.substring(cursorIdx);
            newCursorPos = linkStartIndex + strongLink.length;
        }
        onContentChange(newContent);
        setShowAutocomplete(false);
        setActiveWeakLink(null);
        setCursorPosition(newCursorPos);
    };

    const handleKeyDown = (e) => {
        if (!showAutocomplete || searchResults.length === 0) return;
        switch (e.key) {
            case 'ArrowDown': e.preventDefault(); setSelectedIndex(prev => Math.min(prev + 1, searchResults.length - 1)); break;
            case 'ArrowUp': e.preventDefault(); setSelectedIndex(prev => Math.max(prev - 1, 0)); break;
            case 'Enter': case 'Tab': e.preventDefault(); if (searchResults[selectedIndex]) selectResult(searchResults[selectedIndex]); break;
            case 'Escape': e.preventDefault(); setShowAutocomplete(false); setActiveWeakLink(null); break;
            default: break;
        }
    };

    const handleMouseDownOnItem = (e, result) => {
        e.preventDefault();
        selectResult(result);
    };


    return (
        <div className="editor-wrapper">
            <Form.Control
                ref={textareaRef}
                as="textarea"
                value={content}
                onChange={handleContentChange}
                onKeyDown={handleKeyDown}
                onClick={handleSelectionChange}
                onKeyUp={handleSelectionChange}
                onScroll={() => { if (activeWeakLink) setActiveWeakLink(null); }}
                onBlur={() => {
                    setTimeout(() => {
                        if (!document.activeElement.closest('.autocomplete-dropdown')) {
                            setShowAutocomplete(false);
                            setActiveWeakLink(null);
                        }
                    }, 150);
                }}
                style={{ minHeight: '60vh' }}
                className="mb-2"
                autoFocus
            />

            {showAutocomplete && (
                <div ref={dropdownRef} className="autocomplete-dropdown inline" style={{ top: `${dropdownPosition.top + dropdownPosition.height}px`, left: `${dropdownPosition.left}px` }}>
                    {isLoading && <div className="autocomplete-item-info">Searching...</div>}
                    {!isLoading && searchResults.length === 0 && searchTerm.length > 0 && (
                        <div className="autocomplete-item-info">No results for "{searchTerm}".</div>
                    )}
                    {searchResults.map((result, index) => (
                        <div key={result.id} className={`autocomplete-item ${index === selectedIndex ? 'selected' : ''}`} onMouseDown={(e) => handleMouseDownOnItem(e, result)} onMouseEnter={() => setSelectedIndex(index)}>
                            {result.title}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}