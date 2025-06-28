// src/api/axios.jsx

import axios from 'axios';

// Access the environment variable using Vite's syntax.
// When you run `npm run build`, `import.meta.env.VITE_API_URL` will be undefined,
// so it will correctly fall back to '/' for production on PythonAnywhere.
const BASE_URL = import.meta.env.PROD ? '/' : import.meta.env.VITE_API_URL;

console.log(`Build mode is: ${import.meta.env.MODE}. Using API Base URL: ${BASE_URL}`);

const api = axios.create({
  baseURL: BASE_URL,
});

// --- REQUEST INTERCEPTOR ---
// This runs BEFORE every request is sent. It adds the token to the header.
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// --- RESPONSE INTERCEPTOR ---
// This runs AFTER every response is received. It checks for 401 errors.
api.interceptors.response.use(
  (response) => {
    // If the response is successful (2xx), just return it.
    return response;
  },
  (error) => {
    // Check if the error is a 401 Unauthorized error.
    if (error.response && error.response.status === 401) {
      // If it is, our token is invalid. Time to log out.
      console.log('Token is invalid or expired. Logging out.');
      
      // Clean up local storage.
      localStorage.removeItem('token');
      // Add any other localStorage keys you use here.

      // Redirect to the login page.
      window.location.href = '/'; 
    }

    // For any other errors, just pass them along.
    return Promise.reject(error);
  }
);

export default api;