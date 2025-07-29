import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAppContext } from '../../context/AppContext';
import ChatHistoryPanel from './ChatHistoryPanel';
import './Chat.css';

// --- HELFERFUNKTIONEN & ICONS ---

// Client-seitige UUID-Generierung
function generateUUID() {
    if (crypto && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    // Fallback für ältere Browser
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

const CopyIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-clipboard" viewBox="0 0 16 16"><path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1-1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1z"/><path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0z"/></svg> );
const CheckIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-check-lg" viewBox="0 0 16 16"><path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425z"/></svg> );
const DeleteIcon = () => (<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-x-circle" viewBox="0 0 16 16"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/><path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708"/></svg>);

const ResubmitIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-stars" viewBox="0 0 16 16">
        <path d="M7.657 6.247c.11-.33.576-.33.686 0l.645 1.937a2.5 2.5 0 0 0 1.83.98l1.982.288c.337.049.46.48.21.66l-1.432 1.396a2.5 2.5 0 0 0-.743 2.24l.338 1.975c.064.372-.293.658-.6.494l-1.764-.928a2.5 2.5 0 0 0-2.31 0l-1.765.928c-.306.164-.663-.122-.6-.494l.338-1.975a2.5 2.5 0 0 0-.743-2.24L1.13 9.113c-.25-.18-.127-.611.21-.66l1.982-.288a2.5 2.5 0 0 0 1.83-.98l.645-1.937zM3.794 1.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.09 1.09l1.162.387a.217.217 0 0 1 0 .412l-1.162.387c-.51.173-.917.572-1.09 1.09l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.734 1.734 0 0 0 1.148 3.794l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387A1.734 1.734 0 0 0 3.407 1.53l.387-1.162zM10.863.099a.145.145 0 0 1 .274 0l.258.774c.115.346.386.617.732.732l.774.258a.145.145 0 0 1 0 .274l-.774.258a1.156 1.156 0 0 0-.732.732l-.258.774a.145.145 0 0 1-.274 0l-.258-.774a1.156 1.156 0 0 0-.732-.732l-.774-.258a.145.145 0 0 1 0-.274l.774.258c.346-.115.617-.386.732-.732L10.863.1z"/>
    </svg>
);

// --- SUB-KOMPONENTEN ---

const ChatMessage = React.memo(({ message, onResubmitPrompt, isChatLoading, onDelete }) => {
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

    const isTemporary = message.id.startsWith('temp-') || message.status === 'pending';

    return (
        <div className={`message ${message.role} ${isTemporary ? 'pending' : ''}`}>
            <div className="message-header">
                <strong>{isUser ? 'You' : (message.author?.display_name || message.llm_model_source || 'Assistant')}</strong>
                <div className="message-buttons">
                    {!isTemporary && (
                        <button className="btn-icon" onClick={() => onDelete(message.id)} disabled={isChatLoading} title="Delete message">
                            <DeleteIcon />
                        </button>
                    )}
                    {isUser && !isTemporary && (
                        <button className="btn-icon" onClick={() => onResubmitPrompt(message)} disabled={isChatLoading} title="Generate new response for this prompt">
                            <ResubmitIcon />
                        </button>
                    )}
                    {!isUser && (
                        <button className="btn-icon" onClick={handleCopy} disabled={isCopied || !message.content} title={isCopied ? "Copied!" : "Copy"}>
                            {isCopied ? <CheckIcon /> : <CopyIcon />}
                        </button>
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
        activeVault, chatHistory, chatSessionId, setChatSessionId, isChatLoading,
        setIsChatLoading, selectedNodeIds, selectedModel, isLoadingModels,
        startNewChat, loadChatSession, activeSessionTitle, setActiveSessionTitle,
        appendMessage, updateMessage, appendChunkToMessage,
    } = useAppContext();

    const [chatInputValue, setChatInputValue] = useState(() => sessionStorage.getItem('chatInputDraft') || '');
    const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);
    const chatDisplayRef = useRef(null);

    useEffect(() => { sessionStorage.setItem('chatInputDraft', chatInputValue); }, [chatInputValue]);
    useEffect(() => { if (chatDisplayRef.current) { chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight; } }, [chatHistory]);

    const handleNewChat = () => {
        if (chatHistory.length > 0 && !window.confirm("Are you sure? This will start a new conversation.")) return;
        startNewChat();
        setChatInputValue('');
    };

    const handleLoadSession = async (sessionIdToLoad) => {
        if (chatHistory.length > 0 && !window.confirm("Loading a past session will replace the current one. Continue?")) return;
        const success = await loadChatSession(sessionIdToLoad);
        if (success) setIsHistoryPanelOpen(false);
    };

    const handleDeleteMessage = useCallback(async (messageIdToDelete) => {
        if (isChatLoading || !chatSessionId || !activeVault) return;
        if (!window.confirm("Are you sure you want to remove this message from the conversation?")) return;

        updateMessage(messageIdToDelete, { status: 'deleted' });

        setIsChatLoading(true); // Zeige einen Ladezustand

        try {
            const jwtToken = localStorage.getItem('token');
            const response = await fetch(
                `/api/vaults/${activeVault.id}/sessions/${chatSessionId}/messages/${messageIdToDelete}`,
                { method: 'DELETE', headers: { 'Authorization': `Bearer ${jwtToken}` } }
            );
            if (!response.ok) {
                throw new Error(`Server responded with status ${response.status}`);
            }

            // --- NEU: Lade die Session neu, um die neue Sortierung zu erhalten ---
            await loadChatSession(chatSessionId);

        } catch (error) {
            console.error("Failed to delete message:", error);
            alert("Could not delete the message on the server.");
        } finally {
            setIsChatLoading(false); // Ladezustand beenden
        }
    }, [isChatLoading, chatSessionId, activeVault, loadChatSession]);

    const processSseStream = useCallback((reader, tempAssistantId) => {
        const decoder = new TextDecoder();
        let buffer = '';

        const pump = async () => {
            try {
                const { done, value } = await reader.read();
                if (done) {
                    setIsChatLoading(false);
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                let boundary;
                while ((boundary = buffer.indexOf('\n\n')) !== -1) {
                    const eventBlock = buffer.substring(0, boundary);
                    buffer = buffer.substring(boundary + 2);

                    const eventMatch = eventBlock.match(/^event: (.*)$/m);
                    const dataMatch = eventBlock.match(/^data: (.*)$/m);
                    if (dataMatch) {
                        try {
                            const eventType = eventMatch ? eventMatch[1].trim() : 'message';
                            const data = JSON.parse(dataMatch[1].trim());

                            switch (eventType) {
                                case 'user_message_confirmed':
                                    updateMessage(data.client_id, data.server_message);
                                    break;
                                case 'assistant_message_start':
                                    updateMessage(tempAssistantId, data);
                                    break;
                                case 'message':
                                    if (data.id && data.token) {
                                        appendChunkToMessage(data.id, data.token);
                                    }
                                    break;
                                case 'assistant_message_end':
                                    updateMessage(data.id, data);
                                    break;
                                case 'session_updated':
                                    setActiveSessionTitle(data.title);
                                    setIsChatLoading(false);
                                    break;
                                case 'message_status_updated':
                                    updateMessage(data.id, { status: data.status });
                                    break;
                                case 'error':
                                    console.error("SSE Error Event:", data.error);
                                    updateMessage(tempAssistantId, { content: `\n\n**Error:** ${data.error}` });
                                    setIsChatLoading(false);
                                    break;
                                default:
                                    break;
                            }
                        } catch (e) {
                            console.error("Error parsing SSE data:", e, dataMatch[1]);
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
    }, [updateMessage, appendChunkToMessage, setIsChatLoading, setActiveSessionTitle]);

    const handleChatSubmit = async (event) => {
        event.preventDefault();
        if (!chatInputValue.trim() || isChatLoading || !activeVault || !selectedModel) return;

        setIsChatLoading(true);
        const userInput = chatInputValue.trim();
        const clientMessageId = generateUUID();
        const tempAssistantId = `temp-assistant-${generateUUID()}`;

        appendMessage({ id: clientMessageId, role: 'user', content: userInput, status: 'pending' });
        appendMessage({ role: 'assistant', content: '', id: tempAssistantId, llm_model_source: selectedModel, author: { display_name: selectedModel } });
        setChatInputValue('');

        try {
            let currentSessionId = chatSessionId;
            if (!currentSessionId) {
                const jwtToken = localStorage.getItem('token');
                const sessionResponse = await fetch(`/api/vaults/${activeVault.id}/sessions/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${jwtToken}` }
                });
                const sessionData = await sessionResponse.json();
                currentSessionId = sessionData.id;
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
                        client_message_id: clientMessageId
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

    const handleResubmitPrompt = useCallback(async (userMessageToResubmit) => {
        if (isChatLoading || !chatSessionId || !activeVault || !selectedModel) return;

        setIsChatLoading(true);
        const tempAssistantId = `temp-assistant-${generateUUID()}`;
        appendMessage({ role: 'assistant', content: '', id: tempAssistantId, llm_model_source: selectedModel, author: { display_name: selectedModel } });

        try {
            const jwtToken = localStorage.getItem('token');
            const response = await fetch(
                `/api/vaults/${activeVault.id}/sessions/${chatSessionId}/messages/${userMessageToResubmit.id}/retry`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${jwtToken}` },
                    body: JSON.stringify({ model: selectedModel })
                }
            );

            if (!response.ok || !response.body) {
                const errorText = await response.text();
                throw new Error(JSON.parse(errorText).error || 'Request failed');
            }

            processSseStream(response.body.getReader(), tempAssistantId);
        } catch (error) {
            const errorMessage = error.message || "An unexpected error occurred.";
            updateMessage(tempAssistantId, { content: `**Error during resubmit:** ${errorMessage}` });
            setIsChatLoading(false);
        }
    }, [chatSessionId, isChatLoading, selectedModel, activeVault, appendMessage, updateMessage, processSseStream, setIsChatLoading]);

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
                {chatHistory
                    .filter(message => message.status !== 'retried' && message.status !== 'deleted')
                    .map((message) => (
                        <ChatMessage
                            key={message.id}
                            message={message}
                            onResubmitPrompt={handleResubmitPrompt}
                            onDelete={handleDeleteMessage}
                            isChatLoading={isChatLoading}
                        />
                    ))}
            </div>

            <form onSubmit={handleChatSubmit} className="d-flex align-items-start p-2 border-top bg-white gap-2">
                <textarea
                    value={chatInputValue}
                    onChange={(e) => setChatInputValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.shiftKey || e.ctrlKey)) { e.preventDefault(); handleChatSubmit(e); } }}
                    placeholder={isLoadingModels ? "Loading models..." : "Ask about your context (Shift+Enter for new line)"}
                    className="form-control"
                    disabled={isChatLoading || isLoadingModels}
                    rows="2"
                />
                <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isChatLoading || !chatInputValue.trim() || isLoadingModels || !selectedModel}
                    title="Send (Enter)"
                >
                    Send
                </button>
            </form>

            {isHistoryPanelOpen && (<ChatHistoryPanel onLoadSession={handleLoadSession} onClose={() => setIsHistoryPanelOpen(false)} />)}
        </div>
    );
};

export default Chat;