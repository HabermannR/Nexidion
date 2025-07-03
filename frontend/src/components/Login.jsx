import React, { useState, useEffect } from 'react';
import api from '../api/axios'; 
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import styles from './Menu.module.css';

function Login() {
  const [username, setUsername] = useState(''); 
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();


  useEffect(() => {
    if (isAuthenticated) {
      navigate('/nodes');
    }
  }, [isAuthenticated, navigate]);

  // GEÄNDERT: Die Logik für den API-Aufruf
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      // GEÄNDERT: Sende sowohl username als auch password an das Backend
      const response = await api.post('/api/login', { username, password });
      
      // GEÄNDERT: Das Backend sendet jetzt { "access_token": "..." }
      // Wir übergeben den Wert von "access_token" an unsere login-Funktion.
      login(response.data.access_token);

      // Die Weiterleitung passiert automatisch durch den useEffect oben.
      // navigate('/nodes'); // Dieser Aufruf ist nicht mehr nötig.

    } catch (err) {
      console.error('Login failed', err);
      // Gib eine präzisere Fehlermeldung aus
      if (err.response && err.response.status === 401) {
        setError('Benutzername oder Passwort ist falsch.');
      } else {
        setError('Login fehlgeschlagen. Bitte versuche es später erneut.');
      }
    }
  }

  return (
    <div className={styles.MenuWrapper}>
      <div className={styles.MenuContainer}>
        <h2 className={styles.MenuTitle}>Unlock Knowledge Base</h2>
        <form onSubmit={handleSubmit} className={styles.MenuForm}>
          
          {/* NEU: Eingabefeld für den Benutzernamen */}
          <label htmlFor="username" className={styles.Label}>Username</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="z.B. admin"
            required
            className={styles.MenuFormInput}
            autoComplete="username" // Hilft dem Browser beim Ausfüllen
          />

          <label htmlFor="password" className={styles.Label}>Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Passwort eingeben"
            required
            className={styles.MenuFormInput}
            autoComplete="current-password" // Hilft dem Browser beim Ausfüllen
          />

          {error && <p className={styles.errorMessage}>{error}</p>}
          <button type="submit" className={styles.MenuFormButton}>Unlock</button>
        </form>
      </div>
    </div>
  )
}

export default Login;