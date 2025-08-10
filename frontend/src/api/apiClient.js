// src/api/apiClient.js (Die finale Version)

import axios from 'axios';

// Wir setzen die baseURL auf einen relativen Pfad.
// - In der Entwicklung fängt der Vite-Proxy in vite.config.js diesen Pfad ab.
// - In der Produktion fängt der Nginx-Proxy (den wir einrichten) diesen Pfad ab.
const apiClient = axios.create({
    baseURL: '/'
});


// ===================================================================
// Request Interceptor (bleibt gleich)
// ===================================================================
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('authToken');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// ===================================================================
// Response Interceptor (bleibt gleich, wichtig für den 401-Logout)
// ===================================================================
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            console.log('Token ungültig/abgelaufen. Automatischer Logout.');
            localStorage.removeItem('authToken');
            window.location.href = '/';
        }
        return Promise.reject(error);
    }
);

export default apiClient;