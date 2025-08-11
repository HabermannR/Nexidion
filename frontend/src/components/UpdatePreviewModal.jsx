// src/features/workspace/right-panel/UpdatePreviewModal.jsx
import React from 'react';
import { Modal, Button, Spinner } from 'react-bootstrap';
// --- CHANGE: Import the new, more powerful DiffViewer component ---
// The path assumes UpdatePreviewModal is in src/features/workspace/right-panel/
// and DiffViewer is in src/components/
import DiffViewer from './DiffViewer.jsx';

/**
 * A modal to display a side-by-side comparison of old and new content.
 * It's used to preview and accept AI-proposed updates.
 *
 * This component has been refactored to use the shared `DiffViewer` component,
 * which encapsulates all the complex diffing logic and styling.
 *
 * @param {boolean} show - Controls the visibility of the modal.
 * @param {function} onHide - Function to call when the modal is requested to be closed.
 * @param {function} onAccept - Function to call when the "Accept" button is clicked.
 * @param {string} oldContent - The original content to display on the left.
 * @param {string} newContent - The proposed new content to display on the right.
 * @param {boolean} isUpdating - If true, shows a spinner on the accept button.
 */
export default function UpdatePreviewModal({ show, onHide, onAccept, oldContent, newContent, isUpdating }) {
    // Detect the current theme to pass it down to the DiffViewer.
    const useDarkTheme = document.documentElement.getAttribute('data-bs-theme') === 'dark';

    return (
        <Modal show={show} onHide={onHide} size="xl" centered backdrop="static">
            <Modal.Header closeButton>
                <Modal.Title>AI Update Proposal</Modal.Title>
            </Modal.Header>
            {/* --- CHANGE: The body now contains only the DiffViewer component. --- */}
            {/* The p-0 class is removed from Modal.Body as DiffViewer handles its own layout. */}
            <Modal.Body>
                <DiffViewer
                    oldContent={oldContent}
                    newContent={newContent}
                    oldTitle="Original Content" // Provide context-specific titles
                    newTitle="Proposed Changes"
                    useDarkTheme={useDarkTheme}
                    // All other complex props like splitView, styles, compareMethod, etc.
                    // are now handled internally by the DiffViewer component.
                />
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onHide} disabled={isUpdating}>
                    Cancel
                </Button>
                <Button variant="primary" onClick={onAccept} disabled={isUpdating}>
                    {isUpdating ? (
                        <>
                            <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" />
                            <span className="ms-1">Saving...</span>
                        </>
                    ) : 'Accept & Save'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
}