import React from 'react';
import { Link, useNavigate } from 'react-router-dom';

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
  const { isLoggedIn, logout } = useAuth();

  const {
    vaults,
    activeVault,
    changeActiveVault,
    isLoadingVaults,
    validModels,
    selectedModel,
    changeSelectedModel,
    isLoadingModels
  } = useAppContext();


  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const handleVaultChange = (vaultId) => {
    const newActiveVault = vaults.find(v => v.id === parseInt(vaultId));
    if (newActiveVault) {
      changeActiveVault(newActiveVault);
      // KORREKTUR 1: Navigiere zur Basis-URL der ausgewählten Vault.
      // Die NodeList-Komponente unter dieser Route leitet dann korrekt weiter.
      navigate(`/vaults/${vaultId}`, { replace: true });
    }
  };

  const getCurrentModelName = () => {
    if (isLoadingModels || !selectedModel) return 'Lade...';

    const currentModel = validModels.find(m => m.id === selectedModel);

    return currentModel ? currentModel.name : 'Modell wählen';
  };
  return (
      <Navbar bg="dark" variant="dark" expand="lg" className="px-3">
        {/* KORREKTUR 2: Der Link des Logos muss ebenfalls dynamisch sein.
            Er verweist auf die Basis-URL der aktuell aktiven Vault.
            Als Fallback, falls keine Vault aktiv ist, leiten wir zu den Vault-Einstellungen. */}
        <Navbar.Brand as={Link} to={activeVault ? `/vaults/${activeVault.id}` : '/settings/vaults'}>
          <img src={logo} width="30" height="30" className="d-inline-block align-top me-2" alt="CorteXtract Logo" />
          {activeVault ? activeVault.name : 'Wissensbasis'}
        </Navbar.Brand>

        <Navbar.Toggle aria-controls="basic-navbar-nav" />

        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="ms-auto align-items-center">
            {isLoggedIn && (
                <>
                  {/* Vault-Dropdown (unverändert in der Logik) */}
                  <NavDropdown
                      title={
                        isLoadingVaults ? <><Spinner as="span" animation="border" size="sm" /> Lade...</>
                            : (activeVault ? `Vault: ${activeVault.name}` : "Kein Vault")
                      }
                      id="vault-nav-dropdown"
                      className="me-lg-3"
                      onSelect={handleVaultChange}
                      menuVariant="dark"
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

                  {/* LLM-Dropdown (unverändert) */}
                  <NavDropdown
                      title={`LLM: ${getCurrentModelName()}`}
                      id="llm-nav-dropdown"
                      className="me-lg-3"
                      onSelect={changeSelectedModel}
                      disabled={isLoadingModels}
                      menuVariant="dark"
                  >
                    {isLoadingModels ? (
                        <NavDropdown.Item disabled>Modelle werden geladen...</NavDropdown.Item>
                    ) : (
                        validModels.map(model => (
                            <NavDropdown.Item
                                key={model.id}
                                eventKey={model.id}
                                active={selectedModel === model.id}
                            >
                              {model.name}
                            </NavDropdown.Item>
                        ))
                    )}
                    {validModels.length === 0 && !isLoadingModels && (
                        <NavDropdown.Item disabled>Keine Modelle gefunden</NavDropdown.Item>
                    )}
                  </NavDropdown>

                  {/* Logout-Button (unverändert) */}
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
