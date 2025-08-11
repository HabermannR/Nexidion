import { createContext, useContext } from 'react';

// 1. Erzeugt einen leeren "Datenkanal" oder "Teleporter-System".
const WorkspaceDataContext = createContext(null);

// 2. Erstellt einen einfachen, wiederverwendbaren Hook, um Daten aus dem Kanal abzugreifen.
//    Dies ist eine "Best Practice", um die Nutzung zu vereinfachen.
export const useWorkspaceData = () => {
    const context = useContext(WorkspaceDataContext);
    if (!context) {
        // Dieser Fehler hilft uns, falls wir vergessen, den Provider zu verwenden.
        throw new Error('useWorkspaceData must be used within a WorkspaceDataProvider');
    }
    return context;
};

// 3. Exportiert den "Sende-Teil" des Teleporters.
export const WorkspaceDataProvider = WorkspaceDataContext.Provider;