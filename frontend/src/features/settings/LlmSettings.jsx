// src/features/settings/LlmSettings.jsx

import React, { useState, useEffect } from 'react';
// Import useSearchParams
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useWorkspaceStore } from '../workspace/workspaceStore';
import { Container, Card, Button, Form as BootstrapForm, Table, Alert, Spinner } from 'react-bootstrap';
import { useLlmModels } from './useLlmModels.js';
import { useVaultQuery } from '../vaults/hooks/useVaultQuery'; // The dedicated V4 hook
import './LlmSettings.css';

export default function LlmSettings() {
    const navigate = useNavigate();
    // Read the vaultId from the URL query string (e.g., ?vaultId=1)
    const [searchParams] = useSearchParams();
    const vaultId = searchParams.get('vaultId');

    const lastValidPathForThisVault = useWorkspaceStore(state =>
        state.lastValidPaths ? state.lastValidPaths[vaultId] : null
    );

    // Fetch the vault's data using the ID. This query will only run if vaultId is present.
    const { data: activeVault, isLoading: isVaultLoading, isError: isVaultError } = useVaultQuery(vaultId);

    const setChatModel = useWorkspaceStore(state => state.setChatModel);
    const setTitleModel = useWorkspaceStore(state => state.setTitleModel);
    const chatModel = useWorkspaceStore(state => state.chatModel);
    const titleModel = useWorkspaceStore(state => state.titleModel);

    const {
        availableModels,
        isLoading: areModelsLoading,
        isError: areModelsError
    } = useLlmModels();

    // --- LOCAL UI STATE ---
    const [selectedChatLlmId, setSelectedChatLlmId] = useState('');
    const [selectedTitleLlmId, setSelectedTitleLlmId] = useState('');
    const [alert, setAlert] = useState(null);

    // --- SYNC GLOBAL STATE TO LOCAL UI STATE ---
    useEffect(() => {
        if (chatModel) {
            setSelectedChatLlmId(chatModel.id);
        }
        if (titleModel) {
            setSelectedTitleLlmId(titleModel.id);
        }
    }, [chatModel, titleModel]);

    // --- ACTIONS ---
    const handleSubmit = (e) => {
        e.preventDefault();
        const newChatModel = availableModels?.find(m => m.id === selectedChatLlmId);
        const newTitleModel = availableModels?.find(m => m.id === selectedTitleLlmId);

        if (newChatModel) setChatModel(newChatModel);
        if (newTitleModel) setTitleModel(newTitleModel);

        // This navigation is safe because the component would not have rendered
        // this part of the code if activeVault was not available.
        // KORREKTUR: Die Variable `lastValidWorkspacePath` existierte nicht. Es muss `lastValidPathForThisVault` sein.
        navigate(lastValidPathForThisVault || `/vaults/${activeVault.id}`);
    };

    const handleBackClick = () => {
        // KORREKTUR: Die Variable `lastValidWorkspacePath` existierte nicht. Es muss `lastValidPathForThisVault` sein.
        navigate(lastValidPathForThisVault || `/vaults/${activeVault.id}`);
    };

    // --- RENDER LOGIC WITH ROBUST GUARD CLAUSES ---

    // 1. Handle initial loading state for the primary data (the vault itself)
    if (isVaultLoading) {
        return (
            <Container className="py-4 text-center">
                <Spinner animation="border" />
                <p className="mt-2">Lade Vault-Informationen...</p>
            </Container>
        );
    }

    // 2. Handle any network/server errors for the primary data
    if (isVaultError) {
        return (
            <Container className="py-4">
                <Alert variant="danger">
                    Fehler: Die Informationen für diese Vault konnten nicht geladen werden. Bitte versuchen Sie es später erneut.
                </Alert>
            </Container>
        );
    }

    // 3. Handle the case where the API call was successful but returned no data (e.g., vault not found)
    if (!activeVault) {
        return (
            <Container className="py-4">
                <Alert variant="warning">
                    Vault mit der ID "{vaultId}" konnte nicht gefunden werden.
                </Alert>
            </Container>
        );
    }

    // --- FULL COMPONENT RENDER ---
    // If we reach this point, `activeVault` is guaranteed to be a valid object.
    return (
        <Container className="py-4 llm-settings-scroll-container">
            <div className="d-flex justify-content-between align-items-center mb-4">
                {/* This line is now completely safe */}
                <h2>LLM-Einstellungen für "{activeVault.name}"</h2>
                <Button onClick={handleBackClick} variant="secondary">
                    Zurück zum Workspace
                </Button>
            </div>

            {alert && <Alert variant={alert.type} onClose={() => setAlert(null)} dismissible>{alert.message}</Alert>}

            <Card>
                <Card.Header as="h5">Standard-LLMs auswählen</Card.Header>
                <BootstrapForm onSubmit={handleSubmit}>
                    <Card.Body>
                        {areModelsLoading ? (
                            <div className="text-center p-4"><Spinner animation="border" /> Lade Modelle...</div>
                        ) : areModelsError ? (
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
                                {availableModels?.map(llm => (
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
                            disabled={areModelsLoading || !selectedChatLlmId || !selectedTitleLlmId}
                        >
                            Einstellungen speichern
                        </Button>
                    </Card.Footer>
                </BootstrapForm>
            </Card>
        </Container>
    );
}