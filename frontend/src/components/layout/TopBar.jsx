import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation, useParams } from 'react-router-dom';

// Context-Hooks
import { useAuth } from '../../context/AuthContext';
import { useAppContext } from '../../context/AppContext';

// Bootstrap-Komponenten
import Navbar from 'react-bootstrap/Navbar';
import Nav from 'react-bootstrap/Nav';
import Button from 'react-bootstrap/Button';
import NavDropdown from 'react-bootstrap/NavDropdown';
import Spinner from 'react-bootstrap/Spinner';

// Assets
import logo from '../../assets/logo.svg';

function TopBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();
  const { isLoggedIn, logout } = useAuth();
  
  // VAULT-FIX: Holen der Vault-spezifischen Daten und Funktionen aus dem AppContext
  const { vaults, activeVault, changeActiveVault, isLoadingVaults } = useAppContext();

  // LLM-Modell Management
  const validModels = [
    { id: 'claude-sonnet-4-20250514', name: 'claude sonnet 4' },
    { id: 'gpt-4o', name: 'GPT-4o' },
    { id: 'o4-mini-2025-04-16', name: 'o4 mini' },
    { id: 'gpt-4.1-mini-2025-04-14', name: 'GPT-4.1' },
    { id: 'gemini-2.5-pro', name: 'gemini-2.5-pro' },
	{ id: 'local', name: 'local' }
  ];

  const getInitialModel = () => {
    const storedModel = localStorage.getItem('selectedModel');
    return storedModel && validModels.some(m => m.id === storedModel) ? storedModel : validModels[0].id;
  };

  const [selectedModel, setSelectedModel] = useState(getInitialModel());

  useEffect(() => {
    localStorage.setItem('selectedModel', selectedModel);
  }, [selectedModel]);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  // Handler für den Wechsel des Vaults im Dropdown
  const handleVaultChange = (vaultId) => {
    const newActiveVault = vaults.find(v => v.id === parseInt(vaultId));
    if (newActiveVault) {
        changeActiveVault(newActiveVault);
        
        // Immer zur Node-Liste navigieren beim Vault-Wechsel
        // Das verhindert 404-Fehler durch nicht existierende Node-IDs
        navigate('/nodes', { replace: true });
    }
  };

  // Handler für den Wechsel des LLM-Modells
  const handleModelChange = (modelId) => {
    setSelectedModel(modelId);
  };

  // Hilfsfunktion um den aktuellen Modellnamen zu bekommen
  const getCurrentModelName = () => {
    const currentModel = validModels.find(m => m.id === selectedModel);
    return currentModel ? currentModel.name : 'Modell wählen';
  };

  return (
    <Navbar bg="dark" variant="dark" expand="lg" className="px-3">
        <Navbar.Brand as={Link} to="/nodes">
          <img
            src={logo}
            width="30"
            height="30"
            className="d-inline-block align-top me-2"
            alt="CorteXtract Logo"
          />
          {activeVault ? activeVault.name : 'Wissensbasis'}
        </Navbar.Brand>
        
        <Navbar.Toggle aria-controls="basic-navbar-nav" />

        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="ms-auto align-items-center">
            {isLoggedIn && (
              <>
                {/* Vault-Dropdown */}
                <NavDropdown 
                    title={
                        isLoadingVaults ? (
                            <><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> Lade...</>
                        ) : (
                            activeVault ? `Vault: ${activeVault.name}` : "Kein Vault ausgewählt"
                        )
                    } 
                    id="vault-nav-dropdown" 
                    className="me-lg-3"
                    onSelect={handleVaultChange}
                >
                    {vaults.map(vault => (
                        <NavDropdown.Item 
                            key={vault.id} 
                            eventKey={vault.id}
                            active={activeVault?.id === vault.id}
                        >
                            {vault.name}
                        </NavDropdown.Item>
                    ))}
                    {vaults.length === 0 && !isLoadingVaults && (
                        <NavDropdown.Item disabled>Keine Vaults gefunden</NavDropdown.Item>
                    )}
                    <NavDropdown.Divider />
                    <NavDropdown.Item as={Link} to="/settings/vaults">
                        Vaults verwalten...
                    </NavDropdown.Item>
                </NavDropdown>

                {/* LLM-Dropdown im gleichen Stil */}
                <NavDropdown 
                    title={`LLM: ${getCurrentModelName()}`}
                    id="llm-nav-dropdown" 
                    className="me-lg-3"
                    onSelect={handleModelChange}
                >
                    {validModels.map(model => (
                        <NavDropdown.Item 
                            key={model.id} 
                            eventKey={model.id}
                            active={selectedModel === model.id}
                        >
                            {model.name}
                        </NavDropdown.Item>
                    ))}
                </NavDropdown>

                {/* Logout-Button */}
                <Button variant="outline-light" size="sm" onClick={handleLogout}>
                  Log Out
                </Button>
              </>
            )}
            {!isLoggedIn && (
              <Nav.Link as={Link} to="/">Log In</Nav.Link>
            )}
          </Nav>
        </Navbar.Collapse>
    </Navbar>
  );
}

export default TopBar;