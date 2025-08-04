// src/features/vaults/VaultIndexRedirector.jsx

// useEffect, useNavigate und Spinner sind nicht mehr nötig.
import React from 'react';

/**
 * Diese Komponente wird NUR auf der "leeren" Vault-Seite gerendert,
 * wenn der vaultIndexLoader KEIN Umleitungsziel gefunden hat.
 */
export default function VaultIndexRedirector() {
    // Der Loader hat `null` zurückgegeben, also zeigen wir eine Nachricht an.
    // Kein useEffect, keine Navigation, kein Spinner.
    return (
        <div className="p-4 text-muted">
            Wählen Sie einen Knoten aus der Navigation aus oder erstellen Sie einen neuen.
        </div>
    );
}