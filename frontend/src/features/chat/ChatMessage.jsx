// src/features/chat/ChatMessage.jsx

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Chat.css'; // Wir können die Styles hier wiederverwenden

// --- Icons (unverändert) ---
const CopyIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-clipboard" viewBox="0 0 16 16"><path d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1-1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1z"/><path d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0z"/></svg> );
const CheckIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-check-lg" viewBox="0 0 16 16"><path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425z"/></svg> );
const DeleteIcon = () => (<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-x-circle" viewBox="0 0 16 16"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"/><path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708"/></svg>);
const ResubmitIcon = () => ( <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-stars" viewBox="0 0 16 16"><path d="M7.657 6.247c.11-.33.576-.33.686 0l.645 1.937a2.5 2.5 0 0 0 1.83.98l1.982.288c.337.049.46.48.21.66l-1.432 1.396a2.5 2.5 0 0 0-.743 2.24l.338 1.975c.064.372-.293.658-.6.494l-1.764-.928a2.5 2.5 0 0 0-2.31 0l-1.765.928c-.306.164-.663-.122-.6-.494l.338-1.975a2.5 2.5 0 0 0-.743-2.24L1.13 9.113c-.25-.18-.127-.611.21-.66l1.982-.288a2.5 2.5 0 0 0 1.83-.98l.645-1.937zM3.794 1.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.09 1.09l1.162.387a.217.217 0 0 1 0 .412l-1.162.387c-.51.173-.917.572-1.09 1.09l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.734 1.734 0 0 0 1.148 3.794l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387A1.734 1.734 0 0 0 3.407 1.53l.387-1.162zM10.863.099a.145.145 0 0 1 .274 0l.258.774c.115.346.386.617.732.732l.774.258a.145.145 0 0 1 0 .274l-.774.258a1.156 1.156 0 0 0-.732.732l-.258.774a.145.145 0 0 1-.274 0l-.258-.774a1.156 1.156 0 0 0-.732-.732l-.774-.258a.145.145 0 0 1 0-.274l.774.258c.346-.115.617-.386.732-.732L10.863.1z"/></svg>);

const StreamingPlaceholder = () => (
    <span className="streaming-placeholder"></span>
);

export default function ChatMessage({ message, onResubmitPrompt, isChatLoading, onDelete }) {
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

    const isTemporary = message.id.toString().startsWith('temp-') || message.status === 'pending';

    // NEU: Prüfen, ob eine Assistenten-Nachricht gerade streamt (d.h. sie ist temporär und hat noch keinen Inhalt)
    const isStreaming = !isUser && isTemporary && !message.content;

    return (
        <div className={`message ${message.role} ${isTemporary ? 'pending' : ''}`}>
            <div className="message-header">
                <strong>{isUser ? 'You' : (message.llm_model_source || 'Assistant')}</strong>
                <div className="message-buttons">
                    {/* ... Button-Logik bleibt unverändert ... */}
                    {!isTemporary && message.role !== 'user' && (
                        <button className="btn-icon" onClick={() => onDelete(message.id)} disabled={isChatLoading} title="Delete message and subsequent responses">
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

            <div className={`message-content-bubble ${isUser ? 'user-message-content' : 'markdown-content'}`}>
                {/* GEÄNDERTE LOGIK: Zeige den Platzhalter oder den Inhalt an */}
                {isUser
                    ? message.content
                    : ( isStreaming
                            ? <StreamingPlaceholder />
                            : <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    )
                }
            </div>
        </div>
    );
}