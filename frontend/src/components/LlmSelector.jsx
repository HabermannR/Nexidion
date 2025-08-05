// IN: src/components/LlmSelector.jsx

import React, { useEffect } from 'react';
import { NavDropdown, Spinner } from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/apiClient';
import { useWorkspaceStore } from '../features/workspace/workspaceStore';

export default function LlmSelector() {
    // 1. Hole die Zustände und Aktionen aus dem Zustand-Store
    const {
        chatModel,
        titleModel,
        setChatModel,
        setTitleModel,
        initializeModels
    } = useWorkspaceStore();

    // 2. Lade die verfügbaren Modelle von der API
    const { data: availableModels, isLoading } = useQuery({
        queryKey: ['llmModels'], // Globaler, eindeutiger Key
        queryFn: () => apiClient.get('/api/llm/models').then(res => res.data),
        staleTime: Infinity, // Diese Liste ändert sich selten, wir können sie lange cachen
    });

    // 3. Initialisiere die Modelle im Store, sobald sie geladen sind
    useEffect(() => {
        if (availableModels && availableModels.length > 0) {
            initializeModels(availableModels);
        }
    }, [availableModels, initializeModels]);

    // Ladezustand oder wenn die Initialisierung noch nicht abgeschlossen ist
    if (isLoading || !chatModel || !titleModel) {
        return (
            <NavDropdown title="LLM: Lade..." id="llm-selector-dropdown" className="me-lg-3" disabled>
                <NavDropdown.Item disabled>
                    <Spinner as="span" animation="border" size="sm" className="me-2"/>
                    Modelle werden geladen...
                </NavDropdown.Item>
            </NavDropdown>
        );
    }

    return (
        <NavDropdown
            title={`Chat: ${chatModel.name}`}
            id="llm-selector-dropdown"
            className="me-lg-3"
        >
            <NavDropdown.Header>Chat-Modell</NavDropdown.Header>
            {availableModels.map(model => (
                <NavDropdown.Item
                    key={`chat-${model.id}`}
                    active={chatModel.id === model.id}
                    onClick={() => setChatModel(model)}
                >
                    {model.name}
                </NavDropdown.Item>
            ))}

            <NavDropdown.Divider />

            <NavDropdown.Header>Titel-Modell (z.B. für Auto-Titel)</NavDropdown.Header>
            {availableModels.map(model => (
                <NavDropdown.Item
                    key={`title-${model.id}`}
                    active={titleModel.id === model.id}
                    onClick={() => setTitleModel(model)}
                >
                    {model.name}
                </NavDropdown.Item>
            ))}
        </NavDropdown>
    );
}