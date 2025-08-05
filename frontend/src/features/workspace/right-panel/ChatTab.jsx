// IN: src/features/workspace/right-panel/ChatTab.jsx

import React from 'react';
import Chat from './Chat/Chat'; // NEU: Importiere die Haupt-Chat-Komponente

export default function ChatTab() {
    return (
        // Wir brauchen keinen zusätzlichen Wrapper, die Chat-Komponente bringt
        // ihr eigenes Layout mit und soll den gesamten verfügbaren Platz ausfüllen.
        // Das Styling in `Chat.css` (h-100) sorgt dafür.
        <Chat />
    );
}