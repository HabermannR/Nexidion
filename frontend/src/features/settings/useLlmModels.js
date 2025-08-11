// IN: src/hooks/useLlmModels.js

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';

export function useLlmModels() {
    // Holen Sie sich nur die Initialisierungsfunktion aus dem Store
    const initializeModels = useWorkspaceStore(state => state.initializeModels);

    // Führen Sie den Datenabruf genau einmal hier durch
    const { data: availableModels, isLoading, isError } = useQuery({
        queryKey: ['llmModels'],
        queryFn: () => apiClient.get('/api/llm/models').then(res => res.data),
        staleTime: Infinity, // Daten werden aggressiv gecacht
    });

    // Führen Sie die Initialisierung auch nur hier durch
    useEffect(() => {
        // Wenn die Daten erfolgreich geladen wurden, initialisiere sie im Store.
        if (availableModels) {
            initializeModels(availableModels);
        }
    }, [availableModels, initializeModels]);

    // Geben Sie die geladenen Daten und den Status zurück
    return { availableModels, isLoading, isError };
}