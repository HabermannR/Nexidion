// src/components/Chat/Chat.jsx

import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAppContext } from '../../context/AppContext';
import ChatHistoryPanel from './ChatHistoryPanel';
import './Chat.css';
import api from '../../api/axios'; // Wird für die Erstellung der Session benötigt

// --- HELFERFUNKTIONEN & ICONS ---

function generateUUID() {
    if (crypto && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

const CopyIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-clipboard" viewBox="0 0 16 16"><path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1-1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1z"/><path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0z"/></svg> );
const CheckIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-check-lg" viewBox="0 0 16 16"><path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425z"/></svg> );
const RetryIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-arrow-clockwise" viewBox="0 0 16 16"><path fillRule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/><path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/></svg> );
const DeleteIcon = () => (<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-x-circle" viewBox="0 0 16 16"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/><path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708"/></svg>);

// --- SUB-KOMPONENTEN ---

const ChatMessage = React.memo(({ message, onRetry, isChatLoading, onDelete }) => {
    const isUser = message.role === 'user';
    const [isCopied, setIsCopied] = useState(false);

    const handleCopy = () => {
        if (message.content) {
            navigator.clipboard.writeText(message.content).then(() => {
                setIsCopied(true);
                setTimeout(() => setIsCopied(false), 2000);
            });
        }
    };

    return (
        <div className={`message ${message.role}`}>
            <div className="message-header">
                <strong>{isUser ? 'You' : (message.author?.display_name || message.llm_model_source || 'Assistant')}</strong>
                <div className="message-buttons">
                    {/* ===== KORREKTUR HIER ===== */}
                    {/* Dieser Block ist jetzt für BEIDE Nachrichtentypen (User & Assistant) */}
                    {message.id && !message.id.startsWith('temp-') && (
                        <button className="btn-icon" onClick={() => onDelete(message.id)} disabled={isChatLoading} title="Delete message">
                            <DeleteIcon />
                        </button>
                    )}

                    {/* Dieser Block ist NUR für Assistant-Nachrichten */}
                    {!isUser && (
                        <>
                            <button className="btn-icon" onClick={handleCopy} disabled={isCopied} title={isCopied ? "Copied!" : "Copy"}>
                                {isCopied ? <CheckIcon /> : <CopyIcon />}
                            </button>
                            {message.id && !message.id.startsWith('temp-') && (
                                <button className="btn-icon" onClick={() => onRetry(message)} disabled={isChatLoading} title="Retry">
                                    <RetryIcon />
                                </button>
                            )}
                        </>
                    )}
                </div>
            </div>
            <div className={isUser ? 'user-message-content' : 'markdown-content'}>
                {isUser ? message.content : <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>}
            </div>
        </div>
    );
});

// --- HAUPTKOMPONENTE ---

const Chat = () => {
    const {
        activeVault, chatHistory, setChatHistory, chatSessionId, setChatSessionId, isChatLoading,
        setIsChatLoading, selectedNodeIds, selectedModel, isLoadingModels,
        startNewChat, loadChatSession, activeSessionTitle, setActiveSessionTitle,
        appendMessage, updateMessage, appendChunkToMessage, api,
    } = useAppContext();

    const [chatInputValue, setChatInputValue] = useState(() => sessionStorage.getItem('chatInputDraft') || '');
    const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);
    const chatDisplayRef = useRef(null);

    // Side-Effects
    useEffect(() => { sessionStorage.setItem('chatInputDraft', chatInputValue); }, [chatInputValue]);
    useEffect(() => { if (chatDisplayRef.current) { chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight; } }, [chatHistory]);

    // UI-Interaktions-Handler
    const handleNewChat = () => {
        if (window.confirm("Are you sure? This will start a new conversation.")) {
            startNewChat();
            setChatInputValue('');
        }
    };

    const handleLoadSession = async (sessionIdToLoad) => {
        if (chatHistory.length > 0 && !window.confirm("Loading a past session will replace the current one. Continue?")) return;
        const success = await loadChatSession(sessionIdToLoad);
        if (success) setIsHistoryPanelOpen(false);
    };

    const handleDeleteMessage = useCallback(async (messageIdToDelete) => {
        if (isChatLoading || !chatSessionId || !activeVault) return;

        if (!window.confirm("Are you sure you want to remove this message from the conversation?")) {
            return;
        }

        try {
            await api.delete(
                `/api/vaults/${activeVault.id}/sessions/${chatSessionId}/messages/${messageIdToDelete}`
            );
            // UI optimistisch aktualisieren
            setChatHistory(prevHistory => prevHistory.filter(msg => msg.id !== messageIdToDelete));
        } catch (error) {
            console.error("Failed to delete message:", error);
            alert("Could not delete the message. Please try again.");
        }
    }, [isChatLoading, chatSessionId, activeVault, api, setChatHistory]);

    // Kernlogik für die Stream-Verarbeitung
    const processSseStream = useCallback((reader, initialId) => {
        const decoder = new TextDecoder();
        let buffer = '';
        let realAssistantId = initialId.startsWith('temp-') ? null : initialId;

        const pump = async () => {
            try {
                const { done, value } = await reader.read();
                if (done) {
                    if (isChatLoading) setIsChatLoading(false);
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                let boundary;
                while ((boundary = buffer.indexOf('\n\n')) !== -1) {
                    const eventBlock = buffer.substring(0, boundary);
                    buffer = buffer.substring(boundary + 2);

                    const eventMatch = eventBlock.match(/^event: (.*)$/m);
                    const dataMatch = eventBlock.match(/^data: (.*)$/m);
                    const eventType = eventMatch ? eventMatch[1].trim() : 'message';

                    if (dataMatch) {
                        const data = JSON.parse(dataMatch[1].trim());
                        const targetId = realAssistantId || initialId;

                        switch (eventType) {
                            case 'user_message':
                                const tempUserId = chatHistory.find(m => m.id.startsWith('temp-user-'))?.id;
                                if (tempUserId) updateMessage(tempUserId, data);
                                break;
                            case 'assistant_message_start':
                                realAssistantId = data.id;
                                updateMessage(initialId, data);
                                break;
                            case 'message':
                                if (data.id && data.token) appendChunkToMessage(data.id, data.token);
                                break;
                            case 'assistant_message_end':
                                updateMessage(data.id, data);
                                break;
                            case 'session_updated': // <-- NEUES EVENT HANDLING
                                setActiveSessionTitle(data.title);
                                setIsChatLoading(false); // Der Prozess ist jetzt wirklich abgeschlossen
                                break;
                            case 'error':
                                appendChunkToMessage(targetId, `\n\n**Error:** ${data.error}`);
                                setIsChatLoading(false);
                                break;
                            default: break;
                        }
                    }
                }
                pump();
            } catch (error) {
                console.error("Stream reading error:", error);
                setIsChatLoading(false);
            }
        };
        pump();
    }, [chatHistory, updateMessage, appendChunkToMessage, isChatLoading, setIsChatLoading, setActiveSessionTitle]);

    // Handler für das Absenden einer neuen Nachricht
    const handleChatSubmit = async (event) => {
        event.preventDefault();
        if (!chatInputValue.trim() || isChatLoading || !activeVault || !selectedModel) return;

        setIsChatLoading(true);
        const userInput = chatInputValue.trim();
        const tempUserId = `temp-user-${generateUUID()}`;
        const tempAssistantId = `temp-assistant-${generateUUID()}`;

        appendMessage({ role: 'user', content: userInput, id: tempUserId });
        appendMessage({ role: 'assistant', content: '', id: tempAssistantId, llm_model_source: selectedModel, author: { display_name: selectedModel } });
        setChatInputValue('');

        try {
            let currentSessionId = chatSessionId;
            if (!currentSessionId) {
                const sessionResponse = await api.post(`/api/vaults/${activeVault.id}/sessions/`);
                currentSessionId = sessionResponse.data.id;
                setChatSessionId(currentSessionId);
            }

            const jwtToken = localStorage.getItem('token');
            const response = await fetch(
                `/api/vaults/${activeVault.id}/sessions/${currentSessionId}/messages`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${jwtToken}` },
                    body: JSON.stringify({
                        user_input: userInput,
                        node_ids: Array.from(selectedNodeIds),
                        model: selectedModel,
                    })
                }
            );

            if (!response.ok || !response.body) {
                const errorText = await response.text();
                throw new Error(JSON.parse(errorText).error || 'Network response was not ok');
            }

            processSseStream(response.body.getReader(), tempAssistantId);
        } catch (error) {
            const errorMessage = error.message || "An unexpected error occurred.";
            updateMessage(tempAssistantId, { content: `**Error:** ${errorMessage}` });
            setIsChatLoading(false);
        }
    };

    // Handler für den Retry einer Nachricht
    const handleRetry = useCallback(async (messageToRetry) => {
        if (isChatLoading || !chatSessionId || !activeVault || !selectedModel) return;

        setIsChatLoading(true);
        updateMessage(messageToRetry.id, { content: '', llm_model_source: selectedModel, author: { display_name: selectedModel } });

        try {
            const jwtToken = localStorage.getItem('token');
            const response = await fetch(
                `/api/vaults/${activeVault.id}/sessions/${chatSessionId}/messages/${messageToRetry.id}/retry`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${jwtToken}` },
                    body: JSON.stringify({ model: selectedModel })
                }
            );

            if (!response.ok || !response.body) {
                const errorText = await response.text();
                throw new Error(JSON.parse(errorText).error || 'Retry request failed');
            }

            processSseStream(response.body.getReader(), messageToRetry.id);
        } catch (error) {
            const errorMessage = error.message || "An unexpected error occurred.";
            updateMessage(messageToRetry.id, { content: `**Error during retry:** ${errorMessage}` });
            setIsChatLoading(false);
        }
    }, [chatSessionId, isChatLoading, selectedModel, activeVault, updateMessage, processSseStream, setIsChatLoading]);

    return (
        <div className={`d-flex flex-column h-100 bg-light border rounded-3 overflow-hidden chat-window ${isHistoryPanelOpen ? 'history-open' : ''}`}>
            <div className="d-flex justify-content-between align-items-center p-2 border-bottom bg-white">
                <div className="d-flex align-items-center gap-2">
                    <h4 className="h6 mb-0" title={activeSessionTitle || 'Chat'}>
                        {activeSessionTitle ? (activeSessionTitle.length > 30 ? `${activeSessionTitle.substring(0, 28)}...` : activeSessionTitle) : 'Chat'}
                    </h4>
                    {chatSessionId && (<span className="badge bg-success-subtle text-success-emphasis rounded-pill">Active</span>)}
                </div>
                <div className="d-flex gap-2">
                    <button onClick={() => setIsHistoryPanelOpen(true)} className="btn btn-sm btn-outline-secondary" title="View chat history">History</button>
                    <button onClick={handleNewChat} className="btn btn-sm btn-secondary" title="Start a new conversation">New Chat</button>
                </div>
            </div>

            <div className="flex-grow-1 p-3 overflow-auto" ref={chatDisplayRef}>
                {chatHistory.length === 0 && !isChatLoading && (<div className="message assistant"><div className="markdown-content">Select nodes and ask a question!</div></div>)}
                {chatHistory.map((message) => (
                    <ChatMessage
                        key={message.id}
                        message={message}
                        onRetry={handleRetry}
                        onDelete={handleDeleteMessage}
                        isChatLoading={isChatLoading}
                    />
                ))}
            </div>

            <form onSubmit={handleChatSubmit} className="d-flex align-items-start p-2 border-top bg-white gap-2">
                <textarea
                    value={chatInputValue}
                    onChange={(e) => setChatInputValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.shiftKey) ) { e.preventDefault(); handleChatSubmit(e); } }}
                    placeholder={isLoadingModels ? "Loading models..." : "Ask about your context (Ctrl+Enter for new line)"}
                    className="form-control"
                    disabled={isChatLoading || isLoadingModels}
                    rows="2"
                />
                <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isChatLoading || !chatInputValue.trim() || isLoadingModels || !selectedModel}
                    title="Send (Ctrl+Enter)"
                >
                    Send
                </button>
            </form>

            {isHistoryPanelOpen && (<ChatHistoryPanel onLoadSession={handleLoadSession} onClose={() => setIsHistoryPanelOpen(false)} />)}
        </div>
    );
};

export default Chat;