import {redirect} from 'react-router-dom';
import {checkAuth, logoutUser} from './auth.helpers.js';
import apiClient from '../../api/apiClient.js';

/**
 * Der "Wächter"- und "Lotsen"-Loader.
 * 1. Prüft, ob der User eingeloggt ist.
 * 2. Leitet den User von der Wurzel-URL "/" zur passenden Seite weiter.
 * 3. Lädt die globalen Daten (User, Vaults) für alle geschützten Routen.
 */
export async function protectedLoader({request}) {
    // --- 1. WÄCHTER-FUNKTION ---
    if (!checkAuth()) {
        return redirect('/login');
    }

    try {
        console.log("[Auth Loader] Token gefunden. Validiere und lade globale Daten...");
        const [userResponse, vaultsResponse] = await Promise.all([
            apiClient.get('/api/auth/me'),
            apiClient.get('/api/vaults/')
        ]);

        const user = userResponse.data;
        const vaults = vaultsResponse.data;
        console.log("[Auth Loader] Token ist gültig. Lade geschützte Route.");

        // --- 2. LOTSEN-FUNKTION ---
        // Prüfe, ob wir uns genau auf der Wurzel-URL "/" befinden.
        const url = new URL(request.url);
        if (url.pathname === '/') {
            console.log("[Auth Loader] Auf Wurzel-URL. Entscheide, wohin umgeleitet wird...");
            if (vaults && vaults.length > 0) {
                // Leite zum ersten verfügbaren Vault um.
                const firstVaultId = vaults[0].id;
                return redirect(`/vaults/${firstVaultId}`);
            } else {
                // Kein Vault vorhanden, leite zur NEUEN Verwaltungs-Seite um.
                return redirect('/settings/vaults'); // <-- VON '/welcome/create-vault' GEÄNDERT
            }
        }

        // --- 3. DATEN BEREITSTELLEN ---
        // Für alle anderen URLs (z.B. /vaults/123) einfach die Daten zurückgeben.
        return {user, vaults};

    } catch (error) {
        console.error("[Auth Loader] Token-Validierung fehlgeschlagen.", error.response?.data);
        logoutUser();
        return redirect('/login');
    }
}