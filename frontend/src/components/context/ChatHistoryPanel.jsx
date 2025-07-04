// src/components/chat/ChatHistoryPanel.jsx

import React, { useState, useEffect } from 'react';
import api from '../../api/axios';
import { useAppContext } from '../../context/AppContext';
import './Chat.css';

const ChatHistoryPanel = ({ onLoadSession, onClose }) => {
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const { activeVault } = useAppContext();

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        setError(null);
        setIsLoading(true);
        
        if (!activeVault) {
          setError("No active vault selected.");
          setIsLoading(false);
          return;
        }

        const response = await api.get(`/api/chat/sessions?vault_id=${activeVault.id}`);
        const sortedSessions = response.data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setSessions(sortedSessions);
      } catch (err) {
        console.error("Failed to fetch chat sessions:", err);
        setError("Could not load chat history.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchSessions();
  }, [activeVault]);

  const handleSessionClick = (sessionId) => {
    onLoadSession(sessionId);
  };

  const formatDate = (isoString) => {
    return new Date(isoString).toLocaleString('de-DE', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
  }

  // Prevent scroll events from bubbling up to parent
  const handleScroll = (e) => {
    e.stopPropagation();
  };

  const handleWheel = (e) => {
    e.stopPropagation();
  };

  return (
    <div className="chat-history-panel bg-white border-start shadow-lg d-flex flex-column">
      
      <div className="d-flex justify-content-between align-items-center p-3 border-bottom flex-shrink-0">
        <h3 className="h5 mb-0">Chat History</h3>
        <button onClick={onClose} className="btn-close" title="Close history"></button>
      </div>

      <div 
        className="flex-grow-1 overflow-auto p-2"
        onScroll={handleScroll}
        onWheel={handleWheel}
      >
        {isLoading && <p className="text-center p-3">Loading history...</p>}
        {error && <p className="text-danger p-3">{error}</p>}
        {!isLoading && !error && sessions.length === 0 && (
          <p className="text-muted text-center p-3">No past conversations found.</p>
        )}
        {!isLoading && !error && sessions.length > 0 && (
          <ul className="list-unstyled session-list">
            {sessions.map(session => (
              <li 
                key={session.id} 
                onClick={() => handleSessionClick(session.id)} 
                className="session-item"
                role="button"
              >
                <strong className="session-title d-block text-dark mb-1">{session.title || 'Untitled Chat'}</strong>
                <small className="session-meta d-block text-muted">
                  {formatDate(session.created_at)} ({session.llm_model})
                </small>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

export default ChatHistoryPanel;