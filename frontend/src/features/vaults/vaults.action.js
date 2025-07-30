import { redirect } from 'react-router-dom';
import apiClient from '../../api/apiClient';

export async function createVaultAction({ request }) {
    const formData = await request.formData();
    const vaultName = formData.get('vaultName');

    if (!vaultName || vaultName.trim() === '') {
        return { error: 'Der Name des Vaults darf nicht leer sein.' };
    }

    try {
        const response = await apiClient.post('/api/vaults/', { name: vaultName.trim() });
        const newVault = response.data;
        // Leite den User direkt zum neu erstellten Vault weiter
        return redirect(`/vaults/${newVault.id}`);
    } catch (error) {
        return { error: 'Der Vault konnte nicht erstellt werden.' };
    }
}