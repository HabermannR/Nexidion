// src/features/vaults/vaults.manager.action.js

import {redirect} from 'react-router-dom';
import apiClient from '../../api/apiClient';

export async function vaultManagerAction({request}) {
    const formData = await request.formData();
    const intent = formData.get('intent');

    try {
        switch (intent) {
            // --- NEUER CASE für den Batch-Modus ---
            case 'create_and_stay': {
                const name = formData.get('name');
                if (!name || name.trim() === '') {
                    return {error: 'Der Vault-Name darf nicht leer sein.'};
                }
                await apiClient.post('/api/vaults/', {name: name.trim()});

                // Wir geben eine Erfolgsmeldung und den Intent zurück, damit die UI darauf reagieren kann (z.B. Formular leeren).
                return {success: `Vault "${name}" wurde erfolgreich erstellt.`, intent: 'create_and_stay'};
            }

            // --- Bestehender Case ---
            case 'create': {
                const name = formData.get('name');
                if (!name || name.trim() === '') {
                    return {error: 'Der Vault-Name darf nicht leer sein.'};
                }
                const response = await apiClient.post('/api/vaults/', {name: name.trim()});
                const newVault = response.data;
                return redirect(`/vaults/${newVault.id}`);
            }

            // ... die anderen cases (rename, delete, activate) bleiben unverändert ...
            case 'rename': {
                const vaultId = formData.get('vaultId');
                const newName = formData.get('newName');
                if (!newName || newName.trim() === '') {
                    return {error: 'Der neue Name darf nicht leer sein.'};
                }
                await apiClient.put(`/api/vaults/${vaultId}`, {name: newName.trim()});
                return {success: `Vault wurde erfolgreich in "${newName}" umbenannt.`};
            }

            case 'delete': {
                const vaultIdToDelete = formData.get('vaultId');
                const activeVaultId = formData.get('activeVaultId');
                await apiClient.delete(`/api/vaults/${vaultIdToDelete}`);

                if (vaultIdToDelete === activeVaultId) {
                    const vaultsResponse = await apiClient.get('/api/vaults/');
                    const remainingVaults = vaultsResponse.data;

                    if (remainingVaults.length > 0) {
                        return redirect(`/vaults/${remainingVaults[0].id}`);
                    } else {
                        return redirect('/settings/vaults');
                    }
                }
                return {success: 'Vault wurde erfolgreich gelöscht.'};
            }

            case 'activate': {
                const activeVaultId = formData.get('vaultId');
                return redirect(`/vaults/${activeVaultId}`);
            }

            default: {
                throw new Response('Unknown intent', {status: 400});
            }
        }
    } catch (err) {
        const errorMessage = err.response?.data?.error || 'Ein unbekannter Fehler ist aufgetreten.';
        return {error: errorMessage};
    }
}