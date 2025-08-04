// src/features/vaults/vaults.manager.loader.js

import apiClient from '../../api/apiClient';

export async function vaultManagerLoader() {
    try {
        // Fetch all vaults for the current user
        const vaultsResponse = await apiClient.get('/api/vaults/');
        return {
            vaults: vaultsResponse.data,
            error: null
        };
    } catch (error) {
        console.error("Failed to load vaults:", error);
        // Return an error structure that the component can gracefully handle
        return {
            vaults: [],
            error: "Vaults konnten nicht geladen werden. Bitte versuchen Sie es später erneut."
        };
    }
}