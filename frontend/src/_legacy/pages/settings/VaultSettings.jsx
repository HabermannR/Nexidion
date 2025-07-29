import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../../context/AppContext';
import api from '../../api/axios';

// Bootstrap components
import Container from 'react-bootstrap/Container';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import Card from 'react-bootstrap/Card';
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Table from 'react-bootstrap/Table';
import Modal from 'react-bootstrap/Modal';
import Alert from 'react-bootstrap/Alert';
import Spinner from 'react-bootstrap/Spinner';
import InputGroup from 'react-bootstrap/InputGroup';

function VaultSettings() {
  const navigate = useNavigate();
  const { vaults, activeVault, fetchVaults, changeActiveVault } = useAppContext();
  
  // State für Formulare und Modals
  const [newVaultName, setNewVaultName] = useState('');
  const [editingVault, setEditingVault] = useState(null);
  const [editName, setEditName] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [vaultToDelete, setVaultToDelete] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Erfolgs-/Fehlermeldungen automatisch ausblenden
  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError('');
        setSuccess('');
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  // Neuen Vault erstellen
  const handleCreateVault = async (e) => {
    e.preventDefault();
    if (!newVaultName.trim()) {
      setError('Vault-Name darf nicht leer sein');
      return;
    }

    setIsLoading(true);
    setError('');
    
    try {
      const response = await api.post('/api/vaults', {
        name: newVaultName.trim()
      });
      
      setSuccess(`Vault "${newVaultName}" wurde erfolgreich erstellt`);
      setNewVaultName('');
      await fetchVaults(); // Use fetchVaults instead of refreshVaults
      
    } catch (err) {
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError('Fehler beim Erstellen des Vaults');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Vault umbenennen
  const handleRenameVault = async (e) => {
    e.preventDefault();
    if (!editName.trim()) {
      setError('Vault-Name darf nicht leer sein');
      return;
    }

    setIsLoading(true);
    setError('');
    
    try {
      await api.put(`/api/vaults/${editingVault.id}`, {
        name: editName.trim()
      });
      
      setSuccess(`Vault wurde erfolgreich umbenannt zu "${editName}"`);
      setEditingVault(null);
      setEditName('');
      await fetchVaults(); // Use fetchVaults instead of refreshVaults
      
    } catch (err) {
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError('Fehler beim Umbenennen des Vaults');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Vault löschen
  const handleDeleteVault = async () => {
    if (!vaultToDelete) return;

    setIsLoading(true);
    setError('');
    
    try {
      await api.delete(`/api/vaults/${vaultToDelete.id}`);
      
      setSuccess(`Vault "${vaultToDelete.name}" wurde erfolgreich gelöscht`);
      setShowDeleteModal(false);
      
      // Wenn der gelöschte Vault der aktive war, fetchVaults wird automatisch 
      // den ersten verfügbaren Vault aktivieren
      if (activeVault?.id === vaultToDelete.id) {
        await fetchVaults();
      } else {
        await fetchVaults();
      }
      
      setVaultToDelete(null);
      
    } catch (err) {
      if (err.response?.data?.error) {
        setError(err.response.data.error);
      } else {
        setError('Fehler beim Löschen des Vaults');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Bearbeitung starten
  const startEdit = (vault) => {
    setEditingVault(vault);
    setEditName(vault.name);
  };

  // Bearbeitung abbrechen
  const cancelEdit = () => {
    setEditingVault(null);
    setEditName('');
  };

  // Löschen-Dialog öffnen
  const showDeleteConfirm = (vault) => {
    setVaultToDelete(vault);
    setShowDeleteModal(true);
  };

  // Vault aktivieren
  const handleActivateVault = (vault) => {
    changeActiveVault(vault);
    setSuccess(`Vault "${vault.name}" wurde als aktiv gesetzt`);
  };

  return (
    <Container className="py-4">
      <Row>
        <Col>
          <div className="d-flex justify-content-between align-items-center mb-4">
            <h2>Vault-Verwaltung</h2>
            <Button variant="secondary" onClick={() => navigate('/nodes')}>
              Zurück zu den Nodes
            </Button>
          </div>

          {/* Erfolgs-/Fehlermeldungen */}
          {error && (
            <Alert variant="danger" dismissible onClose={() => setError('')}>
              {error}
            </Alert>
          )}
          {success && (
            <Alert variant="success" dismissible onClose={() => setSuccess('')}>
              {success}
            </Alert>
          )}

          {/* Neuen Vault erstellen */}
          <Card className="mb-4">
            <Card.Header>
              <h5 className="mb-0">Neuen Vault erstellen</h5>
            </Card.Header>
            <Card.Body>
              <Form onSubmit={handleCreateVault}>
                <Row>
                  <Col md={8}>
                    <Form.Group>
                      <Form.Label>Vault-Name</Form.Label>
                      <Form.Control
                        type="text"
                        value={newVaultName}
                        onChange={(e) => setNewVaultName(e.target.value)}
                        placeholder="Namen für den neuen Vault eingeben..."
                        disabled={isLoading}
                      />
                    </Form.Group>
                  </Col>
                  <Col md={4} className="d-flex align-items-end">
                    <Button 
                      type="submit" 
                      variant="primary" 
                      disabled={isLoading || !newVaultName.trim()}
                      className="w-100"
                    >
                      {isLoading ? (
                        <>
                          <Spinner as="span" animation="border" size="sm" /> Erstellen...
                        </>
                      ) : (
                        'Vault erstellen'
                      )}
                    </Button>
                  </Col>
                </Row>
              </Form>
            </Card.Body>
          </Card>

          {/* Bestehende Vaults */}
          <Card>
            <Card.Header>
              <h5 className="mb-0">Bestehende Vaults</h5>
            </Card.Header>
            <Card.Body>
              {vaults.length === 0 ? (
                <Alert variant="info">Keine Vaults vorhanden</Alert>
              ) : (
                <Table responsive>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Status</th>
                      <th>Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vaults.map((vault) => (
                      <tr key={vault.id}>
                        <td>
                          {editingVault?.id === vault.id ? (
                            <Form onSubmit={handleRenameVault}>
                              <InputGroup>
                                <Form.Control
                                  type="text"
                                  value={editName}
                                  onChange={(e) => setEditName(e.target.value)}
                                  disabled={isLoading}
                                />
                                <Button 
                                  type="submit" 
                                  variant="outline-success" 
                                  size="sm"
                                  disabled={isLoading || !editName.trim()}
                                >
                                  ✓
                                </Button>
                                <Button 
                                  variant="outline-secondary" 
                                  size="sm"
                                  onClick={cancelEdit}
                                  disabled={isLoading}
                                >
                                  ✕
                                </Button>
                              </InputGroup>
                            </Form>
                          ) : (
                            <strong>{vault.name}</strong>
                          )}
                        </td>
                        <td>
                          {activeVault?.id === vault.id ? (
                            <span className="badge bg-success">Aktiv</span>
                          ) : (
                            <Button
                              variant="outline-primary"
                              size="sm"
                              onClick={() => handleActivateVault(vault)}
                              disabled={isLoading}
                            >
                              Aktivieren
                            </Button>
                          )}
                        </td>
                        <td>
                          {editingVault?.id === vault.id ? null : (
                            <div className="btn-group" role="group">
                              <Button
                                variant="outline-primary"
                                size="sm"
                                onClick={() => startEdit(vault)}
                                disabled={isLoading}
                              >
                                Umbenennen
                              </Button>
                              <Button
                                variant="outline-danger"
                                size="sm"
                                onClick={() => showDeleteConfirm(vault)}
                                disabled={isLoading || vaults.length === 1}
                                title={vaults.length === 1 ? "Der letzte Vault kann nicht gelöscht werden" : ""}
                              >
                                Löschen
                              </Button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Löschen-Bestätigung Modal */}
      <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Vault löschen</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            Möchten Sie den Vault "<strong>{vaultToDelete?.name}</strong>" wirklich löschen?
          </p>
          <Alert variant="warning">
            <strong>Warnung:</strong> Diese Aktion kann nicht rückgängig gemacht werden. 
            Alle Daten in diesem Vault werden permanent gelöscht.
          </Alert>
        </Modal.Body>
        <Modal.Footer>
          <Button 
            variant="secondary" 
            onClick={() => setShowDeleteModal(false)}
            disabled={isLoading}
          >
            Abbrechen
          </Button>
          <Button 
            variant="danger" 
            onClick={handleDeleteVault}
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Spinner as="span" animation="border" size="sm" /> Löschen...
              </>
            ) : (
              'Vault löschen'
            )}
          </Button>
        </Modal.Footer>
      </Modal>
    </Container>
  );
}

export default VaultSettings;