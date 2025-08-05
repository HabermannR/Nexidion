// IN: src/features/chat/ChatHistoryPanel.jsx (oder wo immer du es ablegst)

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import apiClient from '../../../../api/apiClient';
import { useWorkspaceStore } from '../../workspaceStore';
import './Chat.css'; // Nutze die alten Styles

// --- Icons als wiederverwendbare Komponenten ---
const TrashIcon = () => (<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-trash" viewBox="0 0 16 16"><path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/><path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/></svg>);
const EditIcon = () => (<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-pencil-fill" viewBox="0 0 16 16"><path d="M12.854.146a.5.5 0 0 0-.707 0L10.5 1.793 14.207 5.5l1.647-1.646a.5.5 0 0 0 0-.708zm.646 6.061L9.793 2.5 3.293 9H3.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.207zm-7.468 7.468A.5.5 0 0 1 6 13.5V13h-.5a.5.5 0 0 1-.5-.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.5-.5V10h-.5a.5.5 0 0 1-.175-.032l-.179.178a.5.5 0 0 0-.11.168l-2 5a.5.5 0 0 0 .65.65l5-2a.5.5 0 0 0 .168-.11z"/></svg>);

// Hilfsfunktion außerhalb der Komponente, da sie sich nie ändert
const formatDate = (isoString) => {
    return new Date(isoString).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
}
// ===================================================================
// SUB-KOMPONENTE: SessionItem
// ===================================================================
const SessionItem = ({ session, onSelect, onDelete, onUpdateTitle }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [newTitle, setNewTitle] = useState(session.title);
    const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);

    // isLoading-Zustand wird von den Mutations aus der Hauptkomponente gesteuert
    const { renameMutation, deleteMutation } = { renameMutation: onUpdateTitle, deleteMutation: onDelete };

    const handleSaveTitle = (e) => {
        e.preventDefault();
        if (newTitle.trim() && newTitle !== session.title) {
            renameMutation.mutate({ sessionId: session.id, title: newTitle });
        }
        setIsEditing(false);
    };

    if (isConfirmingDelete) {
        return (
            <li className="session-item session-item-confirm-delete">
                <small className="text-muted">Delete this chat?</small>
                <div>
                    <button onClick={() => deleteMutation.mutate(session.id)} className="btn btn-sm btn-danger me-2" disabled={deleteMutation.isPending}>
                        {deleteMutation.isPending ? '...' : 'Confirm'}
                    </button>
                    <button onClick={() => setIsConfirmingDelete(false)} className="btn btn-sm btn-secondary" disabled={deleteMutation.isPending}>Cancel</button>
                </div>
            </li>
        );
    }

    return (
        <li
            className={`session-item ${isEditing ? 'editing' : ''}`}
            onClick={() => !isEditing && onSelect(session)}
            role="button"
        >
            {isEditing ? (
                <form onSubmit={handleSaveTitle} className="w-100">
                    <input type="text" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} onBlur={handleSaveTitle} className="form-control form-control-sm" autoFocus disabled={renameMutation.isPending} />
                </form>
            ) : (
                <>
                    <div>
                        <strong className="session-title d-block">{session.title || 'Untitled Chat'}</strong>
                        <small className="session-meta d-block">{formatDate(session.created_at)}</small>
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
// HAUPTKOMPONENTE: ChatHistoryPanel
// ===================================================================
export default function ChatHistoryPanel({ onClose }) {
    const { vaultId } = useParams();
    const queryClient = useQueryClient();
    const { startNewChat, setActiveChatSession, activeChatSessionId } = useWorkspaceStore();

    const { data: sessions, isLoading, isError } = useQuery({
        queryKey: ['chatSessions', vaultId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/sessions/`).then(res => res.data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))),
        enabled: !!vaultId,
    });

    const deleteSessionMutation = useMutation({
        mutationFn: (sessionId) => apiClient.delete(`/api/vaults/${vaultId}/sessions/${sessionId}`),
        onSuccess: (data, sessionId) => {
            queryClient.invalidateQueries({ queryKey: ['chatSessions', vaultId] });
            if (sessionId === activeChatSessionId) {
                startNewChat();
            }
        },
    });

    const renameSessionMutation = useMutation({
        mutationFn: ({ sessionId, title }) => apiClient.put(`/api/vaults/${vaultId}/sessions/${sessionId}`, { title }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['chatSessions', vaultId] });
        }
    });

    const handleSelectSession = (session) => {
        setActiveChatSession(session.id, session.title, []);
        onClose();
    };

    return (
        <div className="chat-history-panel bg-white border-start shadow-lg d-flex flex-column">
            <div className="d-flex justify-content-between align-items-center p-3 border-bottom flex-shrink-0">
                <h3 className="h5 mb-0">Chat History</h3>
                <button onClick={onClose} className="btn-close" title="Close history"></button>
            </div>

            <div className="flex-grow-1 overflow-auto p-2">
                {isLoading && <div className="text-center p-3"><div className="spinner-border spinner-border-sm" /></div>}
                {isError && <div className="alert alert-danger mx-2">Could not load chat history.</div>}
                {!isLoading && !isError && sessions?.length === 0 && <p className="text-muted text-center p-3">No past conversations found.</p>}

                {sessions && (
                    <ul className="list-unstyled session-list">
                        {sessions.map(session => (
                            <SessionItem
                                key={session.id}
                                session={session}
                                onSelect={handleSelectSession}
                                onDelete={deleteSessionMutation}
                                onUpdateTitle={renameSessionMutation}
                            />
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}