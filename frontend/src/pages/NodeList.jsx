import React, { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';

function NodeList() {
  const navigate = useNavigate();
  const { vaultId } = useParams();
  const { treeData } = useAppContext();

  useEffect(() => {
    // Nur weiterleiten, wenn die Daten vom Loader schon im Context sind
    if (treeData && treeData.length > 0) {
      const firstNodeId = treeData[0].id;
      navigate(`/vaults/${vaultId}/nodes/${firstNodeId}`, { replace: true });
    }
  }, [treeData, navigate, vaultId]); // Abhängigkeit von treeData ist entscheidend

  return <div>Lade Vault...</div>;
}

export default NodeList;
