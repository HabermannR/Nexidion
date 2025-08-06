import React, { useState, useEffect } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useWorkspaceStore } from '../workspace/workspaceStore';
// shallow is no longer needed because we are selecting granularly
import { Container, Card, Button, Form as BootstrapForm, Table, Alert, Spinner } from 'react-bootstrap';
import apiClient from '../../api/apiClient';

export default function LlmSettings() {
    const { activeVault } = useOutletContext();

    // --- ZUSTAND INTEGRATION (GLOBAL STATE) - THE FIX ---
    // 1. Select actions separately. Zustand guarantees these are stable.
    const setChatModel = useWorkspaceStore(state => state.setChatModel);
    const setTitleModel = useWorkspaceStore(state => state.setTitleModel);

    // 2. Select data separately. The component will only re-render if this data changes.
    const chatModel = useWorkspaceStore(state => state.chatModel);
    const titleModel = useWorkspaceStore(state => state.titleModel);

    // --- LOCAL UI STATE ---
    const [selectedChatLlmId, setSelectedChatLlmId] = useState('');
    const [selectedTitleLlmId, setSelectedTitleLlmId] = useState('');
    const [alert, setAlert] = useState(null);

    // --- DATA FETCHING ---
    const { data: availableLlms, isLoading, isError } = useQuery({
        queryKey: ['llmModels'],
        queryFn: () => apiClient.get('/api/llm/models').then(res => res.data),
        staleTime: Infinity,
    });

    // --- SYNC GLOBAL STATE TO LOCAL UI STATE ---
    // This is now safe. The effect only depends on `chatModel` and `titleModel`.
    // It will not run again just because the component re-rendered.
    useEffect(() => {
        if (chatModel) {
            setSelectedChatLlmId(chatModel.id);
        }
        if (titleModel) {
            setSelectedTitleLlmId(titleModel.id);
        }
    }, [chatModel, titleModel]); // Correct, stable dependencies

    // --- ACTIONS ---
    const handleSubmit = (e) => {
        e.preventDefault();
        const newChatModel = availableLlms?.find(m => m.id === selectedChatLlmId);
        const newTitleModel = availableLlms?.find(m => m.id === selectedTitleLlmId);

        // Use the stable action functions we selected earlier.
        if (newChatModel) {
            setChatModel(newChatModel);
        }
        if (newTitleModel) {
            setTitleModel(newTitleModel);
        }
        setAlert({ type: 'success', message: 'Einstellungen erfolgreich im Browser gespeichert.' });
    };

    return (
        <Container className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>LLM-Einstellungen</h2>
                <Button as={Link} to={activeVault ? `/vaults/${activeVault.id}` : '/'} variant="secondary">
                    Zurück
                </Button>
            </div>

            {alert && <Alert variant={alert.type} onClose={() => setAlert(null)} dismissible>{alert.message}</Alert>}

            <Card>
                <Card.Header as="h5">Standard-LLMs auswählen</Card.Header>
                <BootstrapForm onSubmit={handleSubmit}>
                    <Card.Body>
                        {isLoading ? (
                            <div className="text-center p-4"><Spinner animation="border" /> Lade Modelle...</div>
                        ) : isError ? (
                            <Alert variant="danger">Fehler: Die Liste der verfügbaren LLMs konnte nicht geladen werden.</Alert>
                        ) : (
                            <Table responsive hover className="align-middle">
                                <thead>
                                <tr>
                                    <th>LLM-Modell</th>
                                    <th className="text-center">Standard für Chat</th>
                                    <th className="text-center">Standard für Titel</th>
                                </tr>
                                </thead>
                                <tbody>
                                {availableLlms?.map(llm => (
                                    <tr key={llm.id}>
                                        <td>
                                            <strong>{llm.name}</strong>
                                            {llm.description && <><br/><small className="text-muted">{llm.description}</small></>}
                                        </td>
                                        <td className="text-center">
                                            <BootstrapForm.Check
                                                type="radio"
                                                name="chatLlm"
                                                id={`chat-llm-${llm.id}`}
                                                value={llm.id}
                                                checked={selectedChatLlmId === llm.id}
                                                onChange={(e) => setSelectedChatLlmId(e.target.value)}
                                            />
                                        </td>
                                        <td className="text-center">
                                            <BootstrapForm.Check
                                                type="radio"
                                                name="titleLlm"
                                                id={`title-llm-${llm.id}`}
                                                value={llm.id}
                                                checked={selectedTitleLlmId === llm.id}
                                                onChange={(e) => setSelectedTitleLlmId(e.target.value)}
                                            />
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                            </Table>
                        )}
                    </Card.Body>
                    <Card.Footer className="text-end">
                        <Button
                            type="submit"
                            variant="primary"
                            disabled={isLoading}
                        >
                            Einstellungen speichern
                        </Button>
                    </Card.Footer>
                </BootstrapForm>
            </Card>
        </Container>
    );
}