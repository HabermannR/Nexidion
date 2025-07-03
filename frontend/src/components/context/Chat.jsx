// src/components/Chat/Chat.jsx (VOLLSTÄNDIGE VERSION MIT BOOTSTRAP)

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../../api/axios';
import { useAppContext } from '../../context/AppContext';
import ChatHistoryPanel from './ChatHistoryPanel'; // Stellen Sie sicher, dass dieser Import korrekt ist
import './Chat.css'; // Wir behalten das CSS für spezifische Stile

const Chat = () => {
  // --- STATE MANAGEMENT ---
  const [chatHistory, setChatHistory] = useState(() => {
    try {
      const savedHistory = sessionStorage.getItem('chatHistory');
      return savedHistory ? JSON.parse(savedHistory) : [];
    } catch (error) {
      console.error("Failed to parse chat history from sessionStorage", error);
      return [];
    }
  });

  const [sessionId, setSessionId] = useState(() => sessionStorage.getItem('sessionId') || null);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);

  const { selectedNodeIds, chatInputValue, setChatInputValue } = useAppContext();
  const chatDisplayRef = useRef(null);

  // --- EFFECTS ---
  // Scrollt bei neuen Nachrichten nach unten
  useEffect(() => {
    if (chatDisplayRef.current) {
      chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // Speichert den Chatverlauf bei Änderungen im sessionStorage
  useEffect(() => {
    sessionStorage.setItem('chatHistory', JSON.stringify(chatHistory));
  }, [chatHistory]);

  // Speichert die Session-ID bei Änderungen im sessionStorage
  useEffect(() => {
    if (sessionId) {
      sessionStorage.setItem('sessionId', sessionId);
    } else {
      sessionStorage.removeItem('sessionId');
    }
  }, [sessionId]);

  // --- HANDLERS ---
  const handleNewChat = () => {
    if (window.confirm("Are you sure? This will start a new conversation and clear the current one.")) {
      setChatHistory([]);
      setSessionId(null);
      setChatInputValue('');
    }
  };

  const handleLoadSession = async (sessionIdToLoad) => {
    if (isLoading) return;
    if (chatHistory.length > 0 && !window.confirm("Loading a past session will replace the current one. Continue?")) {
      return;
    }
    setIsLoading(true);
    try {
      const response = await api.get(`/api/chat/sessions/${sessionIdToLoad}`);
      const sessionData = response.data;
      setChatHistory(sessionData.messages || []);
      setSessionId(sessionData.id);
      setChatInputValue('');
    } catch (error) {
      console.error("Failed to load session history:", error);
      alert("Could not load the selected session.");
    } finally {
      setIsLoading(false);
      setIsHistoryPanelOpen(false);
    }
  };

  const handleChatSubmit = async (event) => {
    event.preventDefault();
    if (!chatInputValue.trim() || isLoading) return;

    const userInput = chatInputValue.trim();
    setChatInputValue('');
    setChatHistory(prev => [...prev, { role: 'user', content: userInput }]);
    setIsLoading(true);

    try {
      const endpoint = sessionId ? `/api/chat/sessions/${sessionId}/messages` : '/api/chat/sessions';
      const selectedModel = localStorage.getItem('selectedModel') || 'claude-3-sonnet-20240229';
      const payload = {
        user_input: userInput,
        node_ids: Array.from(selectedNodeIds),
        ...(!sessionId && { model: selectedModel })
      };
      const response = await api.post(endpoint, payload);
      const assistantResponse = response.data;
      setChatHistory(prev => [...prev, { role: 'assistant', content: assistantResponse.content }]);
      if (assistantResponse.session_id && !sessionId) {
        setSessionId(assistantResponse.session_id);
      }
    } catch (error) {
      console.error('Failed to generate chat response', error);
      const errorMessage = error.response?.data?.error || "Sorry, an error occurred. Please try again.";
      setChatHistory(prev => [...prev, { role: 'assistant', content: errorMessage }]);
    } finally {
      setIsLoading(false);
    }
  };


  // --- JSX RENDER ---
  return (
    // Hauptcontainer mit Flexbox für das Layout. `overflow-hidden` ist wichtig.
    // Die Klasse 'history-open' wird für die CSS-Animation des Panels verwendet.
    <div className={`d-flex flex-column h-100 bg-light border rounded-3 overflow-hidden chat-window ${isHistoryPanelOpen ? 'history-open' : ''}`}>
      
      {/* 1. Header: Feste Höhe, flex-shrink: 0 ist implizit */}
      <div className="d-flex justify-content-between align-items-center p-2 border-bottom bg-white">
        <h4 className="h6 mb-0">Chat with Context</h4>
        <div className="d-flex gap-2">
          <button 
            onClick={() => setIsHistoryPanelOpen(true)} 
            className="btn btn-sm btn-outline-secondary" 
            title="View chat history"
          >
            History
          </button>
          {chatHistory.length > 0 && (
            <button 
              onClick={handleNewChat} 
              className="btn btn-sm btn-secondary" 
              title="Start a new conversation"
            >
              New Chat
            </button>
          )}
        </div>
      </div>

      {/* 2. Chat-Anzeigebereich: Wächst, um den verfügbaren Platz zu füllen, und ist scrollbar */}
      <div className="flex-grow-1 p-3 overflow-auto" ref={chatDisplayRef}>
        {chatHistory.length === 0 && (
          <div className="message assistant">
            <div className="markdown-content">Select nodes and ask a question to start a chat!</div>
          </div>
        )}
        {chatHistory.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <strong>{message.role === 'user' ? 'You' : 'Assistant'}:</strong>
            {message.role === 'assistant' ? (
              <div className="markdown-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="user-message-content">{message.content}</div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message assistant">
            <strong>Assistant:</strong>
            <div className="markdown-content">
              <div className="spinner-border spinner-border-sm" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
              <span className="ms-2">Thinking...</span>
            </div>
          </div>
        )}
      </div>

      {/* 3. Eingabeformular: Feste Höhe, am unteren Rand */}
      <form onSubmit={handleChatSubmit} className="d-flex align-items-start p-2 border-top bg-white gap-2">
        <textarea
          value={chatInputValue}
          onChange={(e) => setChatInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleChatSubmit(e);
            }
          }}
          placeholder="Ask about your selected context..."
          className="form-control"
          disabled={isLoading}
          rows="2"
        />
        <button 
          type="submit" 
          className="btn btn-primary" 
          disabled={isLoading || !chatInputValue.trim()}
        >
          Send
        </button>
      </form>

      {/* 4. Das Verlaufs-Panel, das bei Bedarf gerendert wird */}
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