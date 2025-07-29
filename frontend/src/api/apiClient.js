// src/api/apiClient.js

import axios from 'axios';

const apiClient = axios.create({
    baseURL: 'http://localhost:5001',
});

// ===================================================================
// NEU: Der Request Interceptor
// Diese Funktion wird VOR JEDER Anfrage ausgeführt, die apiClient sendet.
// ===================================================================
apiClient.interceptors.request.use(
    (config) => {
        // 1. Hole den Token aus dem Local Storage
        const token = localStorage.getItem('authToken');

        // 2. Wenn ein Token existiert, füge ihn zum Authorization-Header hinzu
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }

        // 3. Gib die (möglicherweise modifizierte) Konfiguration zurück
        return config;
    },
    (error) => {
        // Dies wird nur bei einem Fehler in der Konfiguration ausgelöst
        return Promise.reject(error);
    }
);

export default apiClient;