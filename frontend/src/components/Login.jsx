import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
// NEU: Importiere den AppContext, um die aktive Vault zu setzen
import { useAppContext } from '../context/AppContext';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  // NEU: Hole die Funktion zum Ändern der aktiven Vault aus dem Context
  const { changeActiveVault } = useAppContext();

  // KORREKTUR: Der useEffect Hook wird komplett überarbeitet
  useEffect(() => {
    if (isAuthenticated) {
      // Diese Funktion holt die Vaults und leitet dann weiter.
      const fetchVaultsAndRedirect = async () => {
        try {
          // 1. Lade die Vaults des Benutzers
          const response = await api.get('/api/vaults/'); // Annahme: Dies ist der Endpunkt
          const userVaults = response.data;

          if (userVaults && userVaults.length > 0) {
            // 2. Wenn Vaults existieren, nimm die erste
            const firstVault = userVaults[0];
            changeActiveVault(firstVault); // Setze sie als aktiv im globalen State
            navigate(`/vaults/${firstVault.id}`); // Leite zur korrekten Vault-URL weiter
          } else {
            // 3. Wenn keine Vaults existieren, leite zur Verwaltungsseite
            navigate('/settings/vaults/');
          }
        } catch (err) {
          console.error("Konnte nach dem Login keine Vaults abrufen:", err);
          // Fallback: Leite den Benutzer zu den Einstellungen, damit er nicht stecken bleibt
          navigate('/settings/vaults/');
        }
      };

      fetchVaultsAndRedirect();
    }
    // KORREKTUR: Füge changeActiveVault zur Abhängigkeitsliste hinzu
  }, [isAuthenticated, navigate, changeActiveVault]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    try {
      const response = await api.post('/api/auth/login/', { username, password });
      login(response.data.access_token);
      // Die Weiterleitung wird jetzt vom useEffect oben übernommen.
    } catch (err) {
      console.error('Login fehlgeschlagen', err);
      if (err.response && err.response.status === 401) {
        setError('Benutzername oder Passwort ist falsch.');
      } else {
        setError('Login fehlgeschlagen. Bitte versuche es später erneut.');
      }
    }
  }

  return (
      <div className="d-flex align-items-center justify-content-center vh-100 bg-light">
        <div className="card shadow p-4" style={{ width: '100%', maxWidth: '500px' }}>
          <div className="card-body">
            <h2 className="card-title text-center mb-4">Unlock Knowledge Base</h2>
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="username" className="form-label">Username</label>
                <input
                    id="username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="z.B. admin"
                    required
                    className="form-control form-control-lg"
                    autoComplete="username"
                />
              </div>
              <div className="mb-3">
                <label htmlFor="password" className="form-label">Password</label>
                <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Passwort eingeben"
                    required
                    className="form-control form-control-lg"
                    autoComplete="current-password"
                />
              </div>
              {error && (
                  <div className="alert alert-danger mt-3" role="alert">
                    {error}
                  </div>
              )}
              <button type="submit" className="btn btn-primary w-100 mt-4 py-2">
                Unlock
              </button>
            </form>
          </div>
        </div>
      </div>
  );
};

export default Login;
