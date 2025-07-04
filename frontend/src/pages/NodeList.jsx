import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
// VAULT-FIX: Importiere den useAppContext, um auf den aktiven Vault zuzugreifen
import { useAppContext } from '../context/AppContext';

function NodeList() {
  const navigate = useNavigate();
  // VAULT-FIX: Hole den activeVault und den Ladezustand aus dem Context
  const { activeVault, isLoadingVaults } = useAppContext();

  useEffect(() => {
    // VAULT-FIX: Starte die Logik nur, wenn ein aktiver Vault vorhanden ist.
    // Das verhindert einen Fehler, während die Vaults noch geladen werden.
    if (!activeVault) {
      return; // Nichts tun, wenn kein Vault ausgewählt ist
    }

    const getFirstNodeAndRedirect = async () => {
      try {
        // VAULT-FIX: Füge die vault_id als Parameter zum API-Aufruf hinzu
        const response = await api.get('/api/nodes/tree', {
          params: { vault_id: activeVault.id }
        });
        const treeData = response.data;

        if (treeData && treeData.length > 0) {
          // Verhalten bleibt gleich: zum ersten Node (dem Root-Node) des Vaults weiterleiten
          const firstNodeId = treeData[0].id;
          navigate(`/nodes/${firstNodeId}`, { replace: true });
        } else {
          // Dieser Fall tritt auf, wenn ein Vault leer ist (z.B. neu erstellt).
          // Eine Weiterleitung zu einer "Erstelle deinen ersten Node"-Seite wäre ideal.
          // Fürs Erste ist eine Meldung oder gar keine Aktion in Ordnung.
          console.warn(`Vault ${activeVault.name} hat keine Nodes. Konnte nicht weiterleiten.`);
          // Man könnte hier auch zu einer speziellen Seite navigieren:
          // navigate(`/vault/${activeVault.id}/empty`);
        }
      } catch (error) {
        console.error(`Could not fetch node tree for vault ${activeVault.id}:`, error);
        // Fehlerbehandlung, z.B. eine Fehlerseite anzeigen
      }
    };

    getFirstNodeAndRedirect();
    
    // VAULT-FIX: Der Effekt soll erneut ausgeführt werden, wenn sich der activeVault ändert.
  }, [activeVault, navigate]);

  // VAULT-FIX: Bessere Lade- und Zustandsmeldungen
  if (isLoadingVaults) {
    return <div>Lade Vaults...</div>;
  }

  if (!activeVault) {
    return <div>Kein Vault ausgewählt. Bitte wählen Sie einen Vault in der Top-Bar aus.</div>;
  }
  
  // Diese Komponente zeigt während der Weiterleitung eine kurze Lade-Nachricht.
  return <div>Lade Node-Struktur...</div>;
}

export default NodeList;