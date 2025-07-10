import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAppContext } from '../../context/AppContext';
import ChatHistoryPanel from './ChatHistoryPanel';
import './Chat.css';

// A simple SVG icon for the Retry button
const RetryIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-arrow-clockwise" viewBox="0 0 16 16">
    <path fillRule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/>
    <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/>
  </svg>
);

const ChatMessage = React.memo(({ message, onRetry, isChatLoading }) => {
  const isUser = message.role === 'user';

  // Converts internal model names to user-friendly display names.
  const getModelDisplayName = (llmModel) => {
    if (!llmModel) return 'Assistant';
    switch (true) {
      case llmModel.includes('claude-3-5-sonnet'): return 'Claude 3.5 Sonnet';
      case llmModel.includes('claude-3-sonnet'): return 'Claude 3 Sonnet';
      case llmModel.includes('claude-3-haiku'): return 'Claude 3 Haiku';
      case llmModel.includes('claude-3-opus'): return 'Claude 3 Opus';
      case llmModel.includes('gpt-4o'): return 'GPT-4o';
      case llmModel.includes('gpt-4'): return 'GPT-4';
      case llmModel.includes('gpt-3.5'): return 'GPT-3.5';
      case llmModel.includes('mock'): return '🚀 Mock LLM (Free Test)';
      default: return llmModel.length > 20 ? `${llmModel.substring(0, 20)}...` : llmModel;
    }
  };

  return (
    <div className={`message ${message.role}`}>
      <div className="message-header">
        <strong>{isUser ? 'You' : getModelDisplayName(message.llm_model_source)}</strong>
        {!isUser && message.id && !message.id.startsWith('temp-') && (
          <button
            className="btn btn-sm btn-icon retry-button"
            onClick={() => onRetry(message)}
            disabled={isChatLoading}
            title="Retry this response"
          >
            <RetryIcon />
          </button>
        )}
      </div>
      <div className={isUser ? 'user-message-content' : 'markdown-content'}>
        {isUser ? (
          message.content
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
});

const Chat = () => {
  const {
    selectedNodeIds,
    activeVault,
    chatHistory,
    chatSessionId,
    setChatSessionId,
    isChatLoading,
    setIsChatLoading,
    appendMessage,
    updateMessageContent,
    appendChunkToMessage,
    replaceMessageId,
    startNewChat,
    loadChatSession,
    selectedModel,
    isLoadingModels,
  } = useAppContext();

  const [chatInputValue, setChatInputValue] = useState(
    () => sessionStorage.getItem('chatInputDraft') || ''
  );
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);
  const [isStreamingEnabled, setIsStreamingEnabled] = useState(() => {
    const saved = localStorage.getItem('isStreamingEnabled');
    return saved !== null ? JSON.parse(saved) : true;
  });
  
  const chatDisplayRef = useRef(null);
  const previousVaultIdRef = useRef(activeVault?.id);

  // Persist chat input draft to session storage
  useEffect(() => {
    sessionStorage.setItem('chatInputDraft', chatInputValue);
  }, [chatInputValue]);

  // Auto-scroll to the bottom of the chat on new messages
  useEffect(() => {
    if (chatDisplayRef.current) {
      chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // Persist streaming preference to local storage
  useEffect(() => {
    localStorage.setItem('isStreamingEnabled', JSON.stringify(isStreamingEnabled));
  }, [isStreamingEnabled]);

  // Clear chat input when switching vaults
  useEffect(() => {
    const currentVaultId = activeVault?.id;
    if (currentVaultId !== previousVaultIdRef.current) {
      setChatInputValue('');
      previousVaultIdRef.current = currentVaultId;
    }
  }, [activeVault]);

  // --- HANDLERS ---

  const handleNewChat = () => {
    if (window.confirm("Are you sure? This will start a new conversation and clear the current one.")) {
      startNewChat();
      setChatInputValue('');
    }
  };

  const handleLoadSession = async (sessionIdToLoad) => {
    if (chatHistory.length > 0 && !window.confirm("Loading a past session will replace the current one. Continue?")) {
      return;
    }
    const success = await loadChatSession(sessionIdToLoad);
    if (success) {
      setIsHistoryPanelOpen(false);
    }
  };

  const handleRetry = async (messageToRetry) => {
    if (isChatLoading || !chatSessionId || !messageToRetry.id) return;

    // Defensive check: this should not happen in normal operation.
    if (messageToRetry.id.startsWith('temp-')) {
        console.error('Retry blocked: The message ID is still temporary.', messageToRetry.id);
        updateMessageContent(messageToRetry.id, `\n\n**Error:** Cannot retry. A permanent ID was not assigned to this message.`);
        return;
    }

    const messageId = messageToRetry.id;

    setIsChatLoading(true);
    // Clear the specific message content in the UI before retrying
    updateMessageContent(messageId, '');

    const retryMessage = async (messageId, model = null) => {
      try {
        const jwtToken = localStorage.getItem('token');
        const headers = {
            'Content-Type': 'application/json',
            ...(jwtToken && { 'Authorization': `Bearer ${jwtToken}` })
        };

        const endpoint = `/api/chat/sessions/${chatSessionId}/messages/${messageId}/retry`;

        // Include model in request body if provided
        const requestBody = model ? { model: model } : {};

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Retry failed: ${errorText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });

            if (chunk.includes("error:")) {
                const errorMatch = chunk.match(/error: (.*)/);
                const errorMessage = errorMatch ? errorMatch[1].trim() : "Stream error during retry.";
                appendChunkToMessage(`\n\n**Error:** ${errorMessage}`, messageId);
                break;
            }

            appendChunkToMessage(chunk, messageId);
        }
      } catch (error) {
        console.error('Failed to retry chat response:', error);
        updateMessageContent(messageId, `\n\n**Error:** ${error.message || "An unexpected error occurred."}`);
      } finally {
        setIsChatLoading(false);
      }
    };

    // --- FIX ---
    // 1. Call the function you just defined.
    // 2. The closing brace for handleRetry was missing.
    await retryMessage(messageId, selectedModel);
  }; // <-- THIS CLOSING BRACE WAS MISSING

  
  const handleChatSubmit = async (event) => {
    event.preventDefault();

    if (!chatInputValue.trim() || isChatLoading || !activeVault || !selectedModel) {
      return;
    }
    
    const userInput = chatInputValue.trim();
    const currentSessionId = chatSessionId;
    
    appendMessage({ role: 'user', content: userInput, id: `temp-user-${Date.now()}` });
    setChatInputValue('');
    setIsChatLoading(true);

    const jwtToken = localStorage.getItem('token');
    const headers = { 
      'Content-Type': 'application/json',
      ...(jwtToken && { 'Authorization': `Bearer ${jwtToken}` })
    };

    const payload = {
      user_input: userInput,
      node_ids: Array.from(selectedNodeIds),
      model: selectedModel,
      ...(!currentSessionId && { vault_id: activeVault.id })
    };

    if (isStreamingEnabled) {
      const tempId = `temp-assistant-${Date.now()}`;
      appendMessage({ role: 'assistant', content: '', id: tempId, llm_model_source: selectedModel });
      
      let realMessageId = null; 

      try {
        const endpoint = currentSessionId
          ? `/api/chat/sessions/${currentSessionId}/messages/stream`
          : '/api/chat/sessions/stream';
        
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: headers, 
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
           const errorText = await response.text();
           throw new Error(errorText);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          
          let boundary;
          while ((boundary = buffer.indexOf('\n\n')) !== -1) {
            const messagePart = buffer.substring(0, boundary);
            buffer = buffer.substring(boundary + 2);

            if (messagePart.startsWith("session_id:")) {
                const newSessionId = messagePart.replace("session_id:", "").trim();
                if (!currentSessionId) {
                  setChatSessionId(newSessionId);
                }
            } else if (messagePart.startsWith("message_id:")) {
                const receivedId = messagePart.replace("message_id:", "").trim();
                if (receivedId && !realMessageId) {
                    realMessageId = receivedId;
                    replaceMessageId(tempId, realMessageId);
                }
            } else if (messagePart.includes("error:")) {
                const errorMatch = messagePart.match(/error: (.*)/);
                const errorMessage = errorMatch ? errorMatch[1].trim() : "Stream error.";
                console.error(`Stream error from server: ${errorMessage}`);
                appendChunkToMessage(`\n\n**Error:** ${errorMessage}`, realMessageId || tempId);
            } else if (messagePart) {
                appendChunkToMessage(messagePart, realMessageId || tempId);
            }
          }
        }
        // Process any remaining content in the buffer
        if (buffer) {
            appendChunkToMessage(buffer, realMessageId || tempId);
        }

      } catch (error) {
        console.error('Failed to stream chat response:', error);
        const errorMessage = `\n\n**Error:** ${error.message || "An unexpected error occurred."}`;
        appendChunkToMessage(errorMessage, realMessageId || tempId);
      } finally {
        setIsChatLoading(false);
      }
    } else { // Non-streaming logic
      try {
        // NOTE: Non-streaming API call is not fully implemented.
        console.error("Non-streaming API call not fully implemented in this example.");
        throw new Error("Non-streaming mode is not available.");
      } catch (error) {
        const errorMessage = error.response?.data?.error || "Sorry, an error occurred.";
        appendMessage({ role: 'assistant', content: `**Error:** ${errorMessage}` });
      } finally {
        setIsChatLoading(false);
      }
    }
  };

  // --- RENDER ---
  return (
    <div className={`d-flex flex-column h-100 bg-light border rounded-3 overflow-hidden chat-window ${isHistoryPanelOpen ? 'history-open' : ''}`}>
      <div className="d-flex justify-content-between align-items-center p-2 border-bottom bg-white">
        <div className="d-flex align-items-center gap-2">
            <h4 className="h6 mb-0">Chat with Context</h4>
            {chatSessionId ? (
                <span className="badge bg-success-subtle text-success-emphasis rounded-pill" title={`Continuing session: ${chatSessionId}`}>
                    Active Session
                </span>
            ) : (
                <span className="badge bg-primary-subtle text-primary-emphasis rounded-pill">
                    New Session
                </span>
            )}
        </div>
        <div className="d-flex align-items-center gap-3">
          <div className="form-check form-switch" title="Toggle response streaming">
            <input
              className="form-check-input"
              type="checkbox"
              role="switch"
              id="streamingToggle"
              checked={isStreamingEnabled}
              onChange={e => setIsStreamingEnabled(e.target.checked)}
            />
            <label className="form-check-label small" htmlFor="streamingToggle">Stream</label>
          </div>
          <div className="d-flex gap-2">
            <button onClick={() => setIsHistoryPanelOpen(true)} className="btn btn-sm btn-outline-secondary" title="View chat history">History</button>
            <button onClick={handleNewChat} className="btn btn-sm btn-secondary" title="Start a new conversation">New Chat</button>
          </div>
        </div>
      </div>

       <div className="flex-grow-1 p-3 overflow-auto" ref={chatDisplayRef}>
        {chatHistory.length === 0 && !isChatLoading && (
          <div className="message assistant">
            <div className="markdown-content">Select nodes and ask a question to start a chat!</div>
          </div>
        )}
        {chatHistory.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            onRetry={handleRetry}
            isChatLoading={isChatLoading}
          />
        ))}
        {/* Show spinner only before the first assistant message chunk arrives */}
        {isChatLoading && chatHistory[chatHistory.length - 1]?.role !== 'assistant' && (
             <div className="spinner-border spinner-border-sm" role="status"><span className="visually-hidden">Loading...</span></div>
        )}
      </div>

     <form onSubmit={handleChatSubmit} className="d-flex align-items-start p-2 border-top bg-white gap-2">
        <textarea
          value={chatInputValue}
          onChange={(e) => setChatInputValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); handleChatSubmit(e); } }}
          placeholder={isLoadingModels ? "Loading models..." : "Ask about your selected context..."}
          className="form-control"
          disabled={isChatLoading || isLoadingModels}
          rows="2"
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={isChatLoading || !chatInputValue.trim() || isLoadingModels || !selectedModel}
        >
          Send
        </button>
      </form>

      {isHistoryPanelOpen && (
        <ChatHistoryPanel
          onLoadSession={handleLoadSession}
          onClose={() => setIsHistoryPanelOpen(false)}
        />
      )}
    </div>
  );
};

export default Chat;