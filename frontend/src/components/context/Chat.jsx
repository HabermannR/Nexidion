// src/components/chat/Chat.jsx 

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../../api/axios';
import { useAppContext } from '../../context/AppContext';
import ChatHistoryPanel from './ChatHistoryPanel';
import './Chat.css';

const ChatMessage = React.memo(({ message }) => {
  const isUser = message.role === 'user';

  // Hilfsfunktion für den Display-Namen des LLMs
  const getModelDisplayName = (llmModel) => {
    if (!llmModel) return 'Assistant';
    
    // Vereinfachte Darstellung für gängige Modelle
    if (llmModel.includes('claude-3-5-sonnet')) return 'Claude 3.5 Sonnet';
    if (llmModel.includes('claude-3-sonnet')) return 'Claude 3 Sonnet';
    if (llmModel.includes('claude-3-haiku')) return 'Claude 3 Haiku';
    if (llmModel.includes('claude-3-opus')) return 'Claude 3 Opus';
    if (llmModel.includes('gpt-4o')) return 'GPT-4o';
    if (llmModel.includes('gpt-4')) return 'GPT-4';
    if (llmModel.includes('gpt-3.5')) return 'GPT-3.5';
    
    // Fallback: Zeige die ersten 20 Zeichen des Modellnamens
    return llmModel.length > 20 ? llmModel.substring(0, 20) + '...' : llmModel;
  };

  return (
    <div className={`message ${message.role}`}>
      <strong>{isUser ? 'You' : getModelDisplayName(message.llm_model_source)}:</strong>
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
  // --- 1. GLOBALER ZUSTAND AUS DEM CONTEXT ---
  const {
    selectedNodeIds,
    activeVault,
    chatHistory,
    chatSessionId,
    setChatSessionId,
    isChatLoading,
    setIsChatLoading,
    appendMessage,
    appendStreamChunk,
    startNewChat,
    loadChatSession,
    selectedModel,     
    isLoadingModels,
  } = useAppContext();

  // --- 2. LOKALER UI- & INPUT-ZUSTAND ---
  // Dieser State ist nur für diese Komponente relevant und sorgt für Performance.
  const [chatInputValue, setChatInputValue] = useState(
    () => sessionStorage.getItem('chatInputDraft') || ''
  );
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);
  const [isStreamingEnabled, setIsStreamingEnabled] = useState(() => {
    const saved = localStorage.getItem('isStreamingEnabled');
    return saved !== null ? JSON.parse(saved) : true;
  });
  
  const chatDisplayRef = useRef(null);
  const previousVaultIdRef = useRef(activeVault?.id); // Für den Reset-Check

  // --- 3. EFFEKTE (REAKTIONEN AUF ZUSTANDSÄNDERUNGEN) ---

  // Effekt für den lokalen Input-Entwurf
  useEffect(() => {
    sessionStorage.setItem('chatInputDraft', chatInputValue);
  }, [chatInputValue]);
  
  // Effekt zum automatischen Scrollen
  useEffect(() => {
    if (chatDisplayRef.current) {
      chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // Effekt zum Speichern der Streaming-Einstellung
  useEffect(() => {
    localStorage.setItem('isStreamingEnabled', JSON.stringify(isStreamingEnabled));
  }, [isStreamingEnabled]);
  
  // Effekt, der auf den globalen Vault-Wechsel reagiert und den LOKALEN Input zurücksetzt.
  // Der globale Chat-Verlauf wird bereits im AppContext zurückgesetzt.
  useEffect(() => {
    const currentVaultId = activeVault?.id;
    if (currentVaultId !== previousVaultIdRef.current) {
      setChatInputValue('');
      previousVaultIdRef.current = currentVaultId;
    }
  }, [activeVault]);

  // --- 4. HANDLER (AKTIONEN AUSLÖSEN) ---

  const handleNewChat = () => {
    if (window.confirm("Are you sure? This will start a new conversation and clear the current one.")) {
      startNewChat(); // Ruft die globale Funktion auf
      setChatInputValue(''); // Setzt den lokalen Input zurück
    }
  };

  const handleLoadSession = async (sessionIdToLoad) => {
    if (chatHistory.length > 0 && !window.confirm("Loading a past session will replace the current one. Continue?")) {
      return;
    }
    const success = await loadChatSession(sessionIdToLoad); // Ruft globale Funktion auf
    if (success) {
      setIsHistoryPanelOpen(false);
    }
  };

  // Der Kern: Die Submit-Funktion. Sie nutzt globale Funktionen, um den globalen State zu ändern.
  const handleChatSubmit = async (event) => {
    event.preventDefault();

    // KORRIGIERTE PRÜFUNG
    if (!chatInputValue.trim() || isChatLoading || !activeVault || !selectedModel) {
      if (!selectedModel) {
          // Gibt dem Benutzer nützliches Feedback
          console.warn("Submit blocked: No model selected or models are still loading.");
      }
      return;
	}

    // DIE PROBLEMATISCHE ZEILE WURDE ENTFERNT.
    // Wir verwenden jetzt direkt `selectedModel` aus dem Context.
    
    const userInput = chatInputValue.trim();
    const currentSessionId = chatSessionId;
    const jwtToken = localStorage.getItem('token');
    
    appendMessage({ role: 'user', content: userInput });
    setChatInputValue('');
    setIsChatLoading(true);

    const headers = { 'Content-Type': 'application/json' };
    if (jwtToken) {
      headers['Authorization'] = `Bearer ${jwtToken}`;
    }

    const payload = {
      user_input: userInput,
      node_ids: Array.from(selectedNodeIds),
      // DIESE ZEILE FUNKTIONIERT JETZT PERFEKT, da `selectedModel` immer aktuell ist.
      ...(!currentSessionId && { model: selectedModel, vault_id: activeVault.id })
    };

    if (isStreamingEnabled) {
      // Leere Assistenten-Nachricht als Platzhalter für den Stream hinzufügen
      appendMessage({ role: 'assistant', content: '' });
      
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
		   let errorMessage = errorText; // Fallback
		   try {
			 // Versuche, die JSON-Fehlermeldung zu parsen
			 const errorJson = JSON.parse(errorText);
			 errorMessage = errorJson.msg || JSON.stringify(errorJson);
		   } catch (e) {
			 // Wenn das Parsen fehlschlägt, ist die errorText wahrscheinlich HTML oder einfacher Text.
			 // Wir verwenden sie direkt.
			 console.warn("Could not parse error response as JSON.", e);
		   }
		   throw new Error(errorMessage);
		}
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let newSessionIdFromStream = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          let chunk = decoder.decode(value, { stream: true });
          
          if (!currentSessionId && !newSessionIdFromStream && chunk.startsWith("session_id:")) {
            const parts = chunk.split('\n\n');
            newSessionIdFromStream = parts[0].replace("session_id:", "").trim();
            setChatSessionId(newSessionIdFromStream); // Globale Session-ID setzen
            chunk = parts.slice(1).join('\n\n');
          }

          appendStreamChunk(chunk); // Globalen Chunk anhängen
        }

      } catch (error) {
        console.error('Failed to stream chat response', error);
        appendStreamChunk(`\n\n**Error:** ${error.message || "An unexpected error occurred."}`);
      } finally {
        setIsChatLoading(false);
      }

    } else { // Non-streaming Logik
      try {
        const endpoint = currentSessionId ? `/api/chat/sessions/${currentSessionId}/messages` : '/api/chat/sessions';
        const response = await api.post(endpoint, payload);
        const assistantResponse = response.data;
        
        appendMessage({ role: 'assistant', content: assistantResponse.content });
        if (assistantResponse.session_id && !chatSessionId) {
          setChatSessionId(assistantResponse.session_id);
        }
      } catch (error) {
        const errorMessage = error.response?.data?.error || "Sorry, an error occurred.";
        appendMessage({ role: 'assistant', content: `**Error:** ${errorMessage}` });
      } finally {
        setIsChatLoading(false);
      }
    }
  };

  // --- 5. JSX RENDER ---
  // Das JSX ist rein deklarativ und verwendet die State-Variablen.
  return (
    <div className={`d-flex flex-column h-100 bg-light border rounded-3 overflow-hidden chat-window ${isHistoryPanelOpen ? 'history-open' : ''}`}>
      <div className="d-flex justify-content-between align-items-center p-2 border-bottom bg-white">
        <h4 className="h6 mb-0">Chat with Context</h4>
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
            {chatHistory.length > 0 && (
              <button onClick={handleNewChat} className="btn btn-sm btn-secondary" title="Start a new conversation">New Chat</button>
            )}
          </div>
        </div>
      </div>

       <div className="flex-grow-1 p-3 overflow-auto" ref={chatDisplayRef}>
        {chatHistory.length === 0 && (
          <div className="message assistant">
            <div className="markdown-content">Select nodes and ask a question to start a chat!</div>
          </div>
        )}
        {chatHistory.map((message, index) => (
          <ChatMessage key={`${chatSessionId || 'new'}-${index}`} message={message} />
        ))}
        {isChatLoading && chatHistory[chatHistory.length-1]?.role !== 'assistant' && (
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
          disabled={isChatLoading || isLoadingModels} // Deaktiviert, während Modelle laden
          rows="2"
        />
        <button 
          type="submit" 
          className="btn btn-primary" 
          disabled={isChatLoading || !chatInputValue.trim() || isLoadingModels || !selectedModel} // Umfassende Deaktivierung
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