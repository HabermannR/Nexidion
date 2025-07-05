import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../../api/axios'; // Kept for non-streaming calls
import { useAppContext } from '../../context/AppContext';
import ChatHistoryPanel from './ChatHistoryPanel'; 
import './Chat.css';

// KORREKTUR 1: Neue, memo-isierte Komponente zur Leistungssteigerung
// Diese Komponente wird nur neu gerendert, wenn sich das `message`-Objekt ändert.
// Sie löst auch das Farbproblem (Korrektur 2).
const ChatMessage = React.memo(({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`message ${message.role}`}>
      <strong>{isUser ? 'You' : 'Assistant'}:</strong>
      {/* KORREKTUR 2: Wendet die richtige CSS-Klasse basierend auf der Rolle an */}
      <div className={isUser ? 'user-message-content' : 'markdown-content'}>
        {isUser ? (
          // Benutzernachrichten brauchen i.d.R. kein Markdown, was das Rendering beschleunigt
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
  
  // NEW: State for the streaming toggle, persisted in localStorage
  const [isStreamingEnabled, setIsStreamingEnabled] = useState(() => {
    const saved = localStorage.getItem('isStreamingEnabled');
    // Default to true (streaming on) if not set
    return saved !== null ? JSON.parse(saved) : true;
  });

    // KORREKTUR: Hol diese nicht mehr aus dem Context...
  // const { selectedNodeIds, chatInputValue, setChatInputValue, activeVault } = useAppContext();
  
  // ...sondern hole nur, was du wirklich global brauchst
  const { selectedNodeIds, activeVault } = useAppContext(); 

  // ...und deklariere den Input-State LOKAL!
   const [chatInputValue, setChatInputValue] = useState(
    () => sessionStorage.getItem('chatInputDraft') || ''
  );
  const chatDisplayRef = useRef(null);
  const previousVaultIdRef = useRef();

  // --- EFFECTS ---
  
  useEffect(() => {
    sessionStorage.setItem('chatInputDraft', chatInputValue);
  }, [chatInputValue]);
  
  // Scroll on new messages
  useEffect(() => {
    if (chatDisplayRef.current) {
      chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // Persist history and session ID
  useEffect(() => {
    sessionStorage.setItem('chatHistory', JSON.stringify(chatHistory));
  }, [chatHistory]);

  useEffect(() => {
    if (sessionId) {
      sessionStorage.setItem('sessionId', sessionId);
    } else {
      sessionStorage.removeItem('sessionId');
    }
  }, [sessionId]);

  // NEW: Persist the streaming preference
  useEffect(() => {
    localStorage.setItem('isStreamingEnabled', JSON.stringify(isStreamingEnabled));
  }, [isStreamingEnabled]);
  
  // Clear chat when vault changes
  useEffect(() => {
    const previousVaultId = previousVaultIdRef.current;
    const currentVaultId = activeVault?.id;
    if (currentVaultId && previousVaultId !== undefined && currentVaultId !== previousVaultId) {
      console.log('Vault has changed. Clearing chat state.');
      setChatHistory([]);
      setSessionId(null);
      setChatInputValue(''); // Dies löscht den lokalen State UND den sessionStorage-Draft (wegen des anderen useEffects)
    }
    previousVaultIdRef.current = currentVaultId;
  }, [activeVault]);

  // --- HANDLERS ---
  const handleNewChat = () => {
    if (window.confirm("Are you sure? This will start a new conversation and clear the current one.")) {
      setChatHistory([]);
      setSessionId(null);
      setChatInputValue('');
    }
  };

  const handleLoadSession = async (sessionIdToLoad) => {
    // ... (This function remains unchanged)
    if (isLoading) return;
    if (chatHistory.length > 0 && !window.confirm("Loading a past session will replace the current one. Continue?")) {
      return;
    }
    setIsLoading(true);
    try {
      // Axios is fine here as this is not a streaming request
      const response = await api.get(`/api/chat/sessions/${sessionIdToLoad}`);
      const sessionData = response.data;
      if (activeVault && sessionData.vault_id !== activeVault.id) {
          alert("This chat session belongs to a different vault and cannot be loaded here.");
          return;
      }
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

  // --- CORE LOGIC: REFACTORED CHAT SUBMIT ---
// In Ihrer Chat.jsx Datei

const handleChatSubmit = async (event) => {
    event.preventDefault();
    if (!chatInputValue.trim() || isLoading || !activeVault) return;

    const userInput = chatInputValue.trim();
    const currentSessionId = sessionId;
    const selectedModel = localStorage.getItem('selectedModel') || 'claude-3-sonnet-20240229';
	console.log(selectedModel)
    
    const jwtToken = localStorage.getItem('token'); 
    const headers = {
      'Content-Type': 'application/json',
    };

    if (jwtToken) {
      headers['Authorization'] = `Bearer ${jwtToken}`;
    }

    setChatInputValue('');
    setIsLoading(true);

    const payload = {
      user_input: userInput,
      node_ids: Array.from(selectedNodeIds),
      ...(!currentSessionId && { model: selectedModel, vault_id: activeVault.id })
    };

    if (isStreamingEnabled) {
      setChatHistory(prev => [
        ...prev,
        { role: 'user', content: userInput },
        { role: 'assistant', content: '' }
      ]);
      
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
            let errorMessage = errorText;
            try {
                errorMessage = JSON.parse(errorText).msg || errorText; 
            } catch {
                // keep raw text
            }
            throw new Error(errorMessage);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let newSessionIdFromStream = null;

        // DER try-Block umschließt die while-Schleife
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          let chunk = decoder.decode(value, { stream: true });
          
          if (!currentSessionId && !newSessionIdFromStream && chunk.startsWith("session_id:")) {
            const parts = chunk.split('\n\n');
            newSessionIdFromStream = parts[0].replace("session_id:", "").trim();
            setSessionId(newSessionIdFromStream);
            chunk = parts.slice(1).join('\n\n');
          }

          setChatHistory(prev => {
            const newHistory = [...prev];
            const lastMessage = newHistory[newHistory.length - 1];
            // Wichtig: Erstelle ein NEUES Objekt für die letzte Nachricht,
            // damit React.memo die Änderung erkennt.
            newHistory[newHistory.length - 1] = {
              ...lastMessage,
              content: lastMessage.content + chunk
            };
            return newHistory;
          });
        } // <-- Hier endet die while-Schleife

      } catch (error) { // <-- Der catch-Block gehört zum try-Block darüber
        console.error('Failed to stream chat response', error);
        const errorMessage = error.message || "Sorry, an error occurred.";
        setChatHistory(prev => {
          const newHistory = [...prev];
          // Überprüfen, ob es überhaupt eine letzte Nachricht gibt, sicher ist sicher
          if (newHistory.length > 0) {
            newHistory[newHistory.length - 1].content = `**Error:** ${errorMessage}`;
          }
          return newHistory;
        });
      } finally {
        setIsLoading(false);
      }

    } else {
      // --- NON-STREAMING LOGIC ---
      setChatHistory(prev => [...prev, { role: 'user', content: userInput }]);
      try {
        const endpoint = currentSessionId ? `/api/chat/sessions/${currentSessionId}/messages` : '/api/chat/sessions';
        const response = await api.post(endpoint, payload);
        const assistantResponse = response.data;
        
        setChatHistory(prev => [...prev, { role: 'assistant', content: assistantResponse.content }]);
        if (assistantResponse.session_id && !sessionId) {
          setSessionId(assistantResponse.session_id);
        }
      } catch (error) {
        console.error('Failed to generate chat response', error);
        const errorMessage = error.response?.data?.error || "Sorry, an error occurred.";
        setChatHistory(prev => [...prev, { role: 'assistant', content: `**Error:** ${errorMessage}` }]);
      } finally {
        setIsLoading(false);
      }
    }
  };

  // --- JSX RENDER ---
  return (
    <div className={`d-flex flex-column h-100 bg-light border rounded-3 overflow-hidden chat-window ${isHistoryPanelOpen ? 'history-open' : ''}`}>
      {/* 1. Header with the new toggle switch */}
      <div className="d-flex justify-content-between align-items-center p-2 border-bottom bg-white">
        <h4 className="h6 mb-0">Chat with Context</h4>
        <div className="d-flex align-items-center gap-3">
          {/* NEW: Streaming Toggle */}
          <div className="form-check form-switch" title="Toggle response streaming">
            <input
              className="form-check-input"
              type="checkbox"
              role="switch"
              id="streamingToggle"
              checked={isStreamingEnabled}
              onChange={e => setIsStreamingEnabled(e.target.checked)}
            />
            <label className="form-check-label small" htmlFor="streamingToggle">
              Stream
            </label>
          </div>
          <div className="d-flex gap-2">
            <button onClick={() => setIsHistoryPanelOpen(true)} className="btn btn-sm btn-outline-secondary" title="View chat history">History</button>
            {chatHistory.length > 0 && (
              <button onClick={handleNewChat} className="btn btn-sm btn-secondary" title="Start a new conversation">New Chat</button>
            )}
          </div>
        </div>
      </div>

      {/* 2. Chat display area (Spinner logic removed for simplicity) */}
       <div className="flex-grow-1 p-3 overflow-auto" ref={chatDisplayRef}>
        {chatHistory.length === 0 && (
          <div className="message assistant">
            <div className="markdown-content">Select nodes and ask a question to start a chat!</div>
          </div>
        )}
        {/* KORREKTUR 1: Nutze die neue, performante Komponente */}
        {chatHistory.map((message, index) => (
          <ChatMessage key={index} message={message} />
        ))}
      </div>

      {/* 3. Input form */}
      <form onSubmit={handleChatSubmit} className="d-flex align-items-start p-2 border-top bg-white gap-2">
        <textarea
          value={chatInputValue}
          onChange={(e) => setChatInputValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); handleChatSubmit(e); } }}
          placeholder="Ask about your selected context..."
          className="form-control"
          disabled={isLoading}
          rows="2"
        />
        <button type="submit" className="btn btn-primary" disabled={isLoading || !chatInputValue.trim()}>Send</button>
      </form>

      {/* 4. History Panel */}
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