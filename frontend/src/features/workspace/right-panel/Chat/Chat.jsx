// IN: src/features/chat/Chat.jsx

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import apiClient from '../../../../api/apiClient'; // Pfad anpassen
import { useWorkspaceStore } from '../../workspaceStore'; // Pfad anpassen
import ChatMessage from './ChatMessage';
import ChatHistoryPanel from './ChatHistoryPanel';
import './Chat.css';

// Client-seitige UUID-Generierung
function generateUUID() {
    if (crypto && crypto.randomUUID) { return crypto.randomUUID(); }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

export default function Chat() {
    // 1. SETUP: HOOKS & ZUSTAND
    const { vaultId } = useParams();
    const queryClient = useQueryClient();
    const { setActiveChatTitle, chatModel, titleModel, selectedNodeIds } = useWorkspaceStore();
    const {
        activeChatSessionId, activeChatMessages, activeChatTitle,
        startNewChat, setActiveChatSession, appendMessage, updateMessage, appendChunkToMessage
    } = useWorkspaceStore();
    const [chatInputValue, setChatInputValue] = useState(() => sessionStorage.getItem('chatInputDraft') || '');
    const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);
    const chatDisplayRef = useRef(null);

    // 2. DATENLADUNG & SYNCHRONISATION
    const { data: sessionData } = useQuery({
        queryKey: ['chatHistory', activeChatSessionId],
        queryFn: () => apiClient.get(`/api/vaults/${vaultId}/sessions/${activeChatSessionId}`).then(res => res.data),
        enabled: !!vaultId && !!activeChatSessionId,
    });
    useEffect(() => {
        if (sessionData && Array.isArray(sessionData.messages)) {
            setActiveChatSession(activeChatSessionId, sessionData.title, sessionData.messages);
        }
    }, [sessionData, activeChatSessionId, setActiveChatSession]);
    useEffect(() => { if (chatDisplayRef.current) { chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight; } }, [activeChatMessages]);
    useEffect(() => { sessionStorage.setItem('chatInputDraft', chatInputValue); }, [chatInputValue]);

    // ==========================================================
    // 3. SSE STREAM PROCESSING
    // ==========================================================
    const processSseStream = useCallback((reader, tempAssistantId) => {
        const decoder = new TextDecoder();
        let buffer = '';

        const pump = async () => {
            try {
                const { done, value } = await reader.read();
                if (done) return;

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
                                    if (data.id && data.token) appendChunkToMessage(data.id, data.token);
                                    break;
                                case 'assistant_message_end':
                                case 'message_status_updated':
                                    updateMessage(data.id, data);
                                    break;
                                case 'session_updated':
                                    queryClient.invalidateQueries({ queryKey: ['chatSessions', vaultId] });
                                    if (data.title) {
                                        setActiveChatTitle(data.title);
                                        }
                                    queryClient.invalidateQueries({ queryKey: ['chatSessions', vaultId] });
                                    break;
                                case 'error':
                                    console.error("SSE Error Event:", data.error);
                                    updateMessage(tempAssistantId, { content: `\n\n**Error:** ${data.error}` });
                                    break;
                            }
                        } catch (e) { console.error("Error parsing SSE data:", e, dataMatch[1]); }
                    }
                }
                pump();
            } catch (error) { console.error("Stream reading error:", error); }
        };
        pump();
    }, [updateMessage, appendChunkToMessage, vaultId, queryClient, setActiveChatTitle]);


    // ==========================================================
    // 4. MUTATIONS FÜR ALLE SCHREIBENDEN AKTIONEN
    // ==========================================================
    const getSseAuthHeaders = () => {
        // ==========================================================
        // FINALE, DEFINITIVE KORREKTUR
        // Stelle sicher, dass der Key mit dem apiClient übereinstimmt
        // ==========================================================
        const jwtToken = localStorage.getItem('authToken');

        // console.log("[getSseAuthHeaders] Token from localStorage with key 'authToken':", jwtToken);

        if (!jwtToken) {
            throw new Error("Authentication token ('authToken') not found. Please log in again.");
        }
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${jwtToken}`
        };
    };

    const createAndSendMessageMutation = useMutation({
        mutationFn: async (payload) => {
            let sessionId = activeChatSessionId;

            // 1. Session erstellen (falls nötig) MIT DEM apiClient!
            if (!sessionId) {
                // apiClient fügt den Token automatisch hinzu.
                const sessionResponse = await apiClient.post(`/api/vaults/${vaultId}/sessions/`);
                sessionId = sessionResponse.data.id;
                // Wichtig: Den Store aktualisieren, BEVOR die nächste Anfrage startet
                setActiveChatSession(sessionId, 'New Chat', [payload.userMessage]);
            }

            // 2. Nachricht senden und Stream öffnen (NUR HIER das native fetch)
            const response = await fetch(
                // Wir verwenden die volle URL, um sicherzugehen.
                // Vite's dev-server proxy kümmert sich um die Weiterleitung an Port 5001.
                `/api/vaults/${vaultId}/sessions/${sessionId}/messages`,
                {
                    method: 'POST',
                    headers: getSseAuthHeaders(), // expliziter Auth-Header
                    body: JSON.stringify(payload.apiPayload)
                }
            );

            if (!response.ok || !response.body) {
                const errorText = await response.text();
                try {
                    throw new Error(JSON.parse(errorText).error || 'Network response was not ok');
                } catch {
                    throw new Error(errorText || 'Network response was not ok');
                }
            }
            return { reader: response.body.getReader(), tempAssistantId: payload.tempAssistantId };
        },
        onSuccess: ({ reader, tempAssistantId }) => processSseStream(reader, tempAssistantId),
        onError: (error, variables) => {
            if (variables?.tempAssistantId) {
                updateMessage(variables.tempAssistantId, { content: `**Error:** ${error.message}` });
            }
        }
    });

    // Für retry und delete verwenden wir dieselbe Logik.
    const resubmitMessageMutation = useMutation({
        mutationFn: async ({ messageToResubmit }) => {
            const tempAssistantMessage = { id: `temp-${generateUUID()}`, role: 'assistant', content: '', llm_model_source: chatModel.name };
            appendMessage(tempAssistantMessage);

            const response = await fetch(
                `/api/vaults/${vaultId}/sessions/${activeChatSessionId}/messages/${messageToResubmit.id}/retry`,
                { method: 'POST', headers: getSseAuthHeaders(), body: JSON.stringify({ model: chatModel.id }) }
            );
            if (!response.ok || !response.body) throw new Error(await response.text());
            return { reader: response.body.getReader(), tempAssistantId: tempAssistantMessage.id };
        },
        onSuccess: ({ reader, tempAssistantId }) => processSseStream(reader, tempAssistantId),
        onError: (error, variables) => updateMessage(variables.tempAssistantId, { content: `**Error:** ${error.message}` })
    });

    // FÜR DELETE: Wir nutzen den apiClient, da wir keine Stream-Antwort erwarten.
    const deleteMessageMutation = useMutation({
        mutationFn: (messageId) => apiClient.delete(`/api/vaults/${vaultId}/sessions/${activeChatSessionId}/messages/${messageId}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['chatHistory', activeChatSessionId] });
        }
    });

    const handleChatSubmit = (event) => {
        event.preventDefault();
        if (!chatInputValue.trim() || createAndSendMessageMutation.isPending || !chatModel) return;

        const userInput = chatInputValue.trim();
        const userMessage = { id: generateUUID(), role: 'user', content: userInput, status: 'pending' };
        const tempAssistantMessage = { id: `temp-${generateUUID()}`, role: 'assistant', content: '', llm_model_source: chatModel.name };

        appendMessage(userMessage);
        appendMessage(tempAssistantMessage);
        setChatInputValue('');

        createAndSendMessageMutation.mutate({
            userMessage: userMessage,
            tempAssistantId: tempAssistantMessage.id,
            apiPayload: {
                user_input: userInput,
                node_ids: Array.from(selectedNodeIds),
                model: chatModel.id,
                titleModel: titleModel?.id,
                client_message_id: userMessage.id
            }
        });
    };

    const handleDeleteMessage = (messageId) => {
        if (!window.confirm("Delete this message and its response?")) return;
        deleteMessageMutation.mutate(messageId);
    };

    const handleResubmitPrompt = (message) => {
        if (createAndSendMessageMutation.isPending || resubmitMessageMutation.isPending) return;
        resubmitMessageMutation.mutate({ messageToResubmit: message });
    };

    // ==========================================================
    // 6. RENDER
    // ==========================================================
    const isChatLoading = createAndSendMessageMutation.isPending;

    return (
        <div className={`d-flex flex-column h-100 bg-light border rounded-3 overflow-hidden chat-window ${isHistoryPanelOpen ? 'history-open' : ''}`}>
            <div className="d-flex justify-content-between align-items-center p-2 border-bottom bg-white">
                <div className="d-flex align-items-center gap-2">
                    <h4 className="h6 mb-0" title={activeChatTitle || 'Chat'}>
                        {activeChatTitle ? (activeChatTitle.length > 30 ? `${activeChatTitle.substring(0, 28)}...` : activeChatTitle) : 'Chat'}
                    </h4>
                    {activeChatSessionId && (<span className="badge bg-success-subtle text-success-emphasis rounded-pill">Active</span>)}
                </div>
                <div className="d-flex gap-2">
                    <button onClick={() => setIsHistoryPanelOpen(true)} className="btn btn-sm btn-outline-secondary" title="View chat history">History</button>
                    <button onClick={startNewChat} className="btn btn-sm btn-secondary" title="Start a new conversation">New Chat</button>
                </div>
            </div>

            <div className="flex-grow-1 p-3 overflow-auto" ref={chatDisplayRef}>
                {(activeChatMessages?.length || 0) === 0 && !isChatLoading && (
                    <div className="message assistant"><div className="markdown-content">Select nodes from the tree and ask a question to start a new chat!</div></div>
                )}
                {activeChatMessages?.map((message) => (
                    <ChatMessage
                        key={message.id}
                        message={message}
                        onDelete={handleDeleteMessage}
                        onResubmitPrompt={handleResubmitPrompt}
                        isChatLoading={isChatLoading}
                    />
                    ))}
            </div>

            <form onSubmit={handleChatSubmit} className="d-flex align-items-start p-2 border-top bg-white gap-2">
                <textarea
                    value={chatInputValue}
                    onChange={(e) => setChatInputValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.shiftKey || e.ctrlKey)) { e.preventDefault(); handleChatSubmit(e); } }}
                    placeholder={!chatModel ? "Select a model..." : "Ask a question (Shift+Enter or Ctrl+Enter to send, Enter for new line)"}
                    className="form-control"
                    disabled={isChatLoading || !chatModel}
                    rows="2"
                />
                <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={isChatLoading || !chatInputValue.trim() || !chatModel}
                    title="Send (Enter)"
                >
                    Send
                </button>
            </form>

            {isHistoryPanelOpen && <ChatHistoryPanel onClose={() => setIsHistoryPanelOpen(false)} />}
        </div>
    );
}