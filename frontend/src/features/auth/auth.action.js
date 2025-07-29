// src/features/auth/auth.action.js
import { redirect } from 'react-router-dom';
import apiClient from '../../api/apiClient';

// Diese Action-Funktion ersetzt handleSubmit und den useEffect komplett.
export async function loginAction({ request }) {
    try {
        // 1. Formulardaten aus dem Request extrahieren
        const formData = await request.formData();
        const { username, password } = Object.fromEntries(formData);

        // 2. Login-Versuch
        const loginResponse = await apiClient.post('/api/auth/login/', { username, password });
        const accessToken = loginResponse.data.access_token;

        // WICHTIG: Token speichern. Dies ersetzt deine `login()`-Funktion aus dem AuthContext.
        localStorage.setItem('authToken', accessToken);

        // 3. Vaults für den User abrufen (sofort nach erfolgreichem Login)
        const vaultsResponse = await apiClient.get('/api/vaults/', {
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        const userVaults = vaultsResponse.data;

        // 4. Weiterleitung basierend auf dem Ergebnis anweisen
        if (userVaults && userVaults.length > 0) {
            const firstVault = userVaults[0];
            // Wir leiten direkt zur ersten Vault weiter.
            return redirect(`/vaults/${firstVault.id}`);
        } else {
            // Keine Vaults? Leite zu den Einstellungen, um eine zu erstellen.
            return redirect('/settings/vaults');
        }

    } catch (err) {
        console.error('Login-Action fehlgeschlagen', err);
        if (err.response && err.response.status === 401) {
            // Gib ein Fehlerobjekt zurück. `useActionData` wird es in der Komponente empfangen.
            return { error: 'Benutzername oder Passwort ist falsch.' };
        }
        return { error: 'Ein unerwarteter Fehler ist aufgetreten.' };
    }
}