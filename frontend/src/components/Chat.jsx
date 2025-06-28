import React, { useState, useRef, useEffect } from 'react';
import api from '../api/axios';
import { useAppContext } from '../context/AppContext';
import './Chat.css';

const Chat = () => {
  const [chatHistory, setChatHistory] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { getContextContent, selectedNodeIds } = useAppContext();
  const chatDisplayRef = useRef(null);

  useEffect(() => {
    if (chatDisplayRef.current) {
      chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight;
    }
  }, [chatHistory]);
  
  // NEW: Handler for the Clear button
  const handleClearChat = () => {
    // We can add a confirmation if we want
    if (window.confirm("Are you sure you want to clear the chat history?")) {
      setChatHistory([]);
    }
  };

  const handleChatSubmit = async (event) => {
    event.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userInput = inputValue.trim();
    setInputValue('');
    setChatHistory(prev => [...prev, { role: 'user', content: userInput }]);
    setIsLoading(true);

    try {
      const { content: contextContent } = await getContextContent();
      
      if (selectedNodeIds.size > 0 && !contextContent) {
          throw new Error("Selected nodes but failed to fetch content.");
      }

      const selectedModel = localStorage.getItem('selectedModel') || 'claude-3-sonnet-20240229';
      
      const response = await api.post('/api/chat', {
        user_input: userInput,
        chat_history: chatHistory,
        model: selectedModel,
        context_content: contextContent,
      });

      const assistantResponse = response.data.content;
      setChatHistory(prev => [...prev, { role: 'assistant', content: assistantResponse }]);

    } catch (error) {
      console.error('Failed to generate chat response', error);
      const errorMessage = "Sorry, an error occurred. Please check your selection and try again.";
      setChatHistory(prev => [...prev, { role: 'assistant', content: errorMessage }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-window">
      {/* === HEADER AREA WITH TITLE AND CLEAR BUTTON === */}
      <div className="chat-header">
        <h4>Chat with Context</h4>
        {chatHistory.length > 0 && (
            <button onClick={handleClearChat} className="clear-chat-button">
                Clear
            </button>
        )}
      </div>

      <div className="chat-display" ref={chatDisplayRef}>
        {chatHistory.length === 0 && (
            <div className="message assistant">
                Select nodes and ask a question about them!
            </div>
        )}
        {chatHistory.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            <strong>{message.role === 'user' ? 'You' : 'Assistant'}:</strong>
            <p>{message.content}</p>
          </div>
        ))}
        {isLoading && (
            <div className="message assistant">
                <strong>Assistant:</strong> Thinking...
            </div>
        )}
      </div>

      {/* === THIS IS THE FORM THAT WAS MISSING === */}
      <form onSubmit={handleChatSubmit} className="chat-input-form">
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleChatSubmit(e);
            }
          }}
          placeholder="Ask about your selected context..."
          className="chat-input"
          disabled={isLoading}
          rows="1"
        />
        <button type="submit" className="send-button" disabled={isLoading || !inputValue.trim()}>
          Send
        </button>
      </form>
    </div>
  );
};

export default Chat;