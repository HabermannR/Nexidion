import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api/axios';
import styles from './Menu.module.css';

function ProfilePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('vaultSelect');
  const [vaults, setVaults] = useState(location.state?.vaults || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editingVaultId, setEditingVaultId] = useState(null);
  const [newVaultName, setNewVaultName] = useState('');
  const [vaultName, setVaultName] = useState('');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [selectedVault, setSelectedVault] = useState(null);

  useEffect(() => {
    if (vaults.length === 0) {
      fetchVaults();
    }
  }, []);

  const fetchVaults = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('token');
      const response = await api.get('/api/vaults', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setVaults(response.data.vaults);
    } catch (error) {
      console.error('Failed to fetch vaults', error);
      setError('Failed to fetch vaults. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleVaultSelect = (vault) => {
    localStorage.setItem('currentVault', JSON.stringify(vault));
    navigate('/nodes/summary');
  }

  const handleVaultCreated = (newVault) => {
    setVaults(prevVaults => [...prevVaults, newVault]);
  }

  const getRoleDisplay = (role) => {
    switch(role) {
      case 'admin': return 'Administrator';
      case 'edit': return 'Editor';
      case 'viewer': return 'Viewer';
      default: return 'Unknown';
    }
  };

  const handleRenameClick = (vault) => {
    setEditingVaultId(vault.id);
    setNewVaultName(vault.name);
  };

  const handleRenameSubmit = async (vaultId) => {
    try {
      const token = localStorage.getItem('token');
      await api.put(`/api/vaults/${vaultId}`, { name: newVaultName }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setVaults(prevVaults => prevVaults.map(vault => 
        vault.id === vaultId ? { ...vault, name: newVaultName } : vault
      ));
      setEditingVaultId(null);
    } catch (error) {
      console.error('Failed to rename vault', error);
      setError('Failed to rename vault. Please try again later.');
    }
  };

  const handleNewVaultSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!vaultName.trim()) {
      setError('Vault name is required');
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const response = await api.post('/api/vaults', 
        { name: vaultName },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setVaultName('');
      handleVaultCreated(response.data.vault);
    } catch (error) {
      console.error('Error creating vault:', error);
      setError(error.response?.data?.error || 'Failed to create vault');
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setMessage('');
    if (newPassword !== confirmPassword) {
      setMessage('New passwords do not match');
      return;
    }
    try {
      const token = localStorage.getItem('token');
      const response = await api.post('/api/change-password', 
        { oldPassword, newPassword },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setMessage('Password changed successfully');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      setMessage(error.response?.data?.msg || 'An error occurred');
    }
  };

  const handleVaultSelection = async (vaultId) => {
    if (!vaultId) {
      setSelectedVault(null);
      return;
    }
    try {
      const token = localStorage.getItem('token');
      const response = await api.get(`/api/vaults/${vaultId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSelectedVault(response.data.vault);
    } catch (error) {
      console.error('Failed to fetch vault details:', error);
    }
  };

  const updateUserVaultAccess = async (userId, vaultId, role) => {
    try {
      const token = localStorage.getItem('token');
      await api.post('/api/user-vault-access', 
        { user_id: userId, vault_id: vaultId, role },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      // Refresh the selected vault to show updated access
      handleVaultSelection(vaultId);
    } catch (error) {
      console.error('Failed to update user vault access:', error);
    }
  };
  
  const handleDeleteVault = async (vaultId) => {
  if (window.confirm('Are you sure you want to delete this vault? This action cannot be undone.')) {
    try {
      const token = localStorage.getItem('token');
      await api.delete(`/api/vaults/${vaultId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setVaults(prevVaults => prevVaults.filter(vault => vault.id !== vaultId));
    } catch (error) {
      console.error('Failed to delete vault', error);
      setError('Failed to delete vault. Please try again later.');
    }
  }
};

  const renderVaultSelection = () => (
  <div className={styles.MenuWrapper}>
    <div className={styles.MenuContainer}>
      <h2 className={styles.MenuTitle}>Select Vault</h2>
      {vaults.length === 0 ? (
        <p>No vaults available. Create a new one below.</p>
      ) : (
        <ul className="vault-list">
          {vaults.map(vault => (
            <li className={styles.MenuList} key={vault.id}>
              {editingVaultId === vault.id ? (
                <div>
                  <input 
                    type="text" 
                    value={newVaultName} 
                    onChange={(e) => setNewVaultName(e.target.value)}
                  />
                  <button onClick={() => handleRenameSubmit(vault.id)} className={styles.MenuFormButton}>Save</button>
                  <button onClick={() => setEditingVaultId(null)} className={styles.MenuFormButton}>Cancel</button>
                </div>
              ) : (
                <div>
                  <button onClick={() => handleVaultSelect(vault)} className={styles.MenuFormButton}>
                    {vault.name} (Role: {getRoleDisplay(vault.role)})
                  </button>
                  {vault.role === 'admin' && (
                    <>
                      <button onClick={() => handleRenameClick(vault)} className={styles.MenuFormButton}>Rename</button>
                      <button onClick={() => handleDeleteVault(vault.id)} className={styles.MenuFormButton}>Delete</button>
                    </>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  </div>
);

  const renderNewVault = () => (
  <div className={styles.MenuWrapper}>
    <div className={styles.MenuContainer}>
      <h2 className={styles.MenuTitle}>New Vault</h2>
      <form onSubmit={handleNewVaultSubmit}>
        <input
          type="text"
          value={vaultName}
          onChange={(e) => setVaultName(e.target.value)}
          placeholder="Enter vault name"
          className={styles.MenuFormInput}
        />
        <button type="submit" className={styles.MenuFormButton}>Create Vault</button>
      </form>
      {error && <p className="error-message">{error}</p>}
    </div>
	</div>
  );

  const renderProfileChange = () => (
    <div className={styles.MenuWrapper}>
	<div className={styles.MenuContainer}>
      <h2 className={styles.MenuTitle}>Change Password</h2>
      <form onSubmit={handlePasswordChange} className={styles.MenuForm}>
        <div>
          <label htmlFor="oldPassword" className={styles.Label}>Current Password:</label>
          <input
            type="password"
            id="oldPassword"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            required
            className={styles.MenuFormInput}
          />
        </div>
        <div>
          <label htmlFor="newPassword" className={styles.Label}>New Password:</label>
          <input
            type="password"
            id="newPassword"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            className={styles.MenuFormInput}
          />
        </div>
        <div>
          <label htmlFor="confirmPassword" className={styles.Label}>Confirm New Password:</label>
          <input
            type="password"
            id="confirmPassword"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            className={styles.MenuFormInput}
          />
        </div>
        <button type="submit" className={styles.MenuFormButton}>Change Password</button>
      </form>
      {message && <p className="message">{message}</p>}
    </div>
	</div>
  );

  const renderVaultManagement = () => (
  <div className={styles.MenuWrapper}>
    <div className={styles.MenuContainer}>
      <h2 className={styles.MenuTitle}>Vault Management</h2>
      <div className={styles.vaultSelector}>
        <div className={styles.selectWrapper}>
          <select 
            className={styles.styledSelect}
            onChange={(e) => handleVaultSelection(e.target.value ? parseInt(e.target.value) : null)}
          >
            <option value="">Select a Vault</option>
            {vaults.map(vault => (
              <option key={vault.id} value={vault.id}>{vault.name}</option>
            ))}
          </select>
        </div>
      </div>
      {selectedVault && (
        <div className={styles.vaultUsers}>
          <h3>Users in {selectedVault.name}</h3>
          <table>
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
              </tr>
            </thead>
            <tbody>
              {selectedVault.users.map(user => (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>
                    <div className={styles.selectWrapper}>
                      <select 
                        className={styles.styledSelect}
                        value={user.role}
                        onChange={(e) => updateUserVaultAccess(user.id, selectedVault.id, e.target.value)}
                      >
                        <option value="none">None</option>
                        <option value="viewer">Viewer</option>
                        <option value="edit">Edit</option>
                        <option value="admin">Admin</option>
                      </select>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  </div>
);

  return (
    <div>
      <div className={styles.TabContainer}>
        <button onClick={() => setActiveTab('vaultSelect')} className={`${styles.TabButton} ${activeTab === 'vaultSelect' ? styles.ActiveTab : ''}`}>Vault Select</button>
        <button onClick={() => setActiveTab('newVault')} className={`${styles.TabButton} ${activeTab === 'newVault' ? styles.ActiveTab : ''}`}>New Vault</button>
        <button onClick={() => setActiveTab('vaultManagement')} className={`${styles.TabButton} ${activeTab === 'vaultManagement' ? styles.ActiveTab : ''}`}>Vault Management</button>
        <button onClick={() => setActiveTab('profileChange')} className={`${styles.TabButton} ${activeTab === 'profileChange' ? styles.ActiveTab : ''}`}>Profile Change</button>
      </div>
      {activeTab === 'vaultSelect' && renderVaultSelection()}
      {activeTab === 'newVault' && renderNewVault()}
      {activeTab === 'vaultManagement' && renderVaultManagement()}
      {activeTab === 'profileChange' && renderProfileChange()}
    </div>
  );
}

export default ProfilePage;