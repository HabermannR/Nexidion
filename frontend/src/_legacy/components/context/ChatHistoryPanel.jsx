import React, { useState, useEffect, useCallback } from 'react';
import { useAppContext } from '../../context/AppContext';
import './Chat.css'; // Wir fügen hier die neuen Stile hinzu

// --- Icons als wiederverwendbare Komponenten ---
const TrashIcon = () => (<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-trash" viewBox="0 0 16 16"><path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/><path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/></svg>);
const EditIcon = () => (<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-pencil-fill" viewBox="0 0 16 16"><path d="M12.854.146a.5.5 0 0 0-.707 0L10.5 1.793 14.207 5.5l1.647-1.646a.5.5 0 0 0 0-.708zm.646 6.061L9.793 2.5 3.293 9H3.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.207zm-7.468 7.468A.5.5 0 0 1 6 13.5V13h-.5a.5.5 0 0 1-.5-.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.5-.5V10h-.5a.5.5 0 0 1-.175-.032l-.179.178a.5.5 0 0 0-.11.168l-2 5a.5.5 0 0 0 .65.65l5-2a.5.5 0 0 0 .168-.11z"/></svg>);

// Hilfsfunktion außerhalb der Komponente, da sie sich nie ändert
const formatDate = (isoString) => {
    return new Date(isoString).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
}

// ===================================================================
// NEUE SUB-KOMPONENTE FÜR JEDES LISTENELEMENT
// ===================================================================
const SessionItem = ({ session, onLoadSession, onDeleteSession, onUpdateTitle }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [newTitle, setNewTitle] = useState(session.title);
    const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
    const [isWorking, setIsWorking] = useState(false); // Für Ladezustand pro Element

    const handleSaveTitle = async (e) => {
        e.preventDefault();
        setIsWorking(true);
        await onUpdateTitle(session.id, newTitle);
        setIsEditing(false);
        setIsWorking(false);
    };

    const handleConfirmDelete = async () => {
        setIsWorking(true);
        await onDeleteSession(session.id);
        // Die Komponente wird verschwinden, also kein setIsWorking(false) nötig
    };

    if (isConfirmingDelete) {
        return (
            <li className="session-item session-item-confirm-delete">
                <small className="text-muted">Delete this chat?</small>
                <div>
                    <button onClick={handleConfirmDelete} className="btn btn-sm btn-danger me-2" disabled={isWorking}>
                        {isWorking ? '...' : 'Confirm'}
                    </button>
                    <button onClick={() => setIsConfirmingDelete(false)} className="btn btn-sm btn-secondary" disabled={isWorking}>Cancel</button>
                </div>
            </li>
        );
    }

    return (
        <li
            className={`session-item d-flex justify-content-between align-items-center ${isEditing ? 'editing' : ''}`}
            onClick={() => !isEditing && onLoadSession(session.id)}
            role="button"
            tabIndex="0"
        >
            {isEditing ? (
                <form onSubmit={handleSaveTitle} className="w-100">
                    <input
                        type="text"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        onBlur={handleSaveTitle}
                        className="form-control form-control-sm"
                        autoFocus
                        disabled={isWorking}
                    />
                </form>
            ) : (
                <>
                    <div>
                        <strong className="session-title d-block text-dark mb-1">{session.title || 'Untitled Chat'}</strong>
                        <small className="session-meta d-block text-muted">{formatDate(session.created_at)}</small>
                    </div>
                    <div className="session-item-actions">
                        <button onClick={(e) => { e.stopPropagation(); setIsEditing(true); }} className="btn btn-sm btn-icon" title="Edit title"><EditIcon /></button>
                        <button onClick={(e) => { e.stopPropagation(); setIsConfirmingDelete(true); }} className="btn btn-sm btn-icon-danger" title="Delete session"><TrashIcon /></button>
                    </div>
                </>
            )}
        </li>
    );
};


// ===================================================================
// VERBESSERTE HAUPTKOMPONENTE
// ===================================================================
const ChatHistoryPanel = ({ onLoadSession, onClose }) => {
    const [sessions, setSessions] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    const { activeVault, api, chatSessionId, startNewChat } = useAppContext();

    const fetchSessions = useCallback(async () => {
        if (!activeVault) {
            setSessions([]);
            return;
        }
        try {
            setError(null);
            setIsLoading(true);
            const response = await api.get(`/api/vaults/${activeVault.id}/sessions/`);
            const sortedSessions = response.data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
            setSessions(sortedSessions);
        } catch (err) {
            console.error("Failed to fetch chat sessions:", err);
            setError("Could not load chat history.");
        } finally {
            setIsLoading(false);
        }
    }, [activeVault, api]);

    useEffect(() => {
        fetchSessions();
    }, [fetchSessions]);

    const handleSessionClick = (sessionId) => {
        onLoadSession(sessionId);
        onClose(); // Schließe das Panel nach dem Laden einer Session
    };

    const handleDeleteSession = async (sessionIdToDelete) => {
        try {
            await api.delete(`/api/vaults/${activeVault.id}/sessions/${sessionIdToDelete}`);

            // Optimistisches Update: Entferne sofort aus der Liste
            setSessions(prev => prev.filter(s => s.id !== sessionIdToDelete));

            // NEU: Prüfen, ob die gelöschte Session die aktuell aktive war
            if (sessionIdToDelete === chatSessionId) {
                // Wenn ja, rufen wir die Funktion zum Starten eines neuen Chats auf,
                // die den gesamten Chat-Zustand zurücksetzt.
                startNewChat();
            }
        } catch (err) {
            console.error("Failed to delete chat session:", err);
            setError("Could not delete the session.");
        }
    };

    const handleUpdateTitle = async (sessionId, newTitle) => {
        try {
            // HINWEIS: Du musst einen entsprechenden PUT-Endpunkt im Backend erstellen!
            await api.put(`/api/vaults/${activeVault.id}/sessions/${sessionId}`, { title: newTitle });
            await fetchSessions(); // Lade die Liste neu, um die Änderung zu bestätigen
        } catch (err) {
            console.error("Failed to update session title:", err);
            setError("Could not update the title.");
        }
    };

    return (
        <div className="chat-history-panel bg-white border-start shadow-lg d-flex flex-column" onScroll={e => e.stopPropagation()} onWheel={e => e.stopPropagation()}>
            <div className="d-flex justify-content-between align-items-center p-3 border-bottom flex-shrink-0">
                <h3 className="h5 mb-0">Chat History</h3>
                <button onClick={onClose} className="btn-close" title="Close history"></button>
            </div>

            <div className="flex-grow-1 overflow-auto p-2">
                {isLoading && <div className="text-center p-3"><div className="spinner-border spinner-border-sm" role="status"><span className="visually-hidden">Loading...</span></div></div>}
                {error && <div className="alert alert-danger mx-2">{error}</div>}
                {!isLoading && !error && sessions.length === 0 && (
                    <p className="text-muted text-center p-3">No past conversations found.</p>
                )}
                {!isLoading && !error && sessions.length > 0 && (
                    <ul className="list-unstyled session-list">
                        {sessions.map(session => (
                            <SessionItem
                                key={session.id}
                                session={session}
                                onLoadSession={handleSessionClick}
                                onDeleteSession={handleDeleteSession}
                                onUpdateTitle={handleUpdateTitle}
                            />
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default ChatHistoryPanel;