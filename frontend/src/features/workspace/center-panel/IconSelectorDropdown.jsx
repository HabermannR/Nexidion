// src/features/nodes/ui/IconSelectorDropdown.jsx (KORRIGIERT)

import React from 'react';
import { Dropdown } from 'react-bootstrap';
import { useMutation, useQueryClient } from '@tanstack/react-query'; // NEU
import apiClient from '../../../api/apiClient'; // NEU

// Datenstruktur für die Icons, gruppiert nach Kategorien
const iconGroups = [
    {
        title: 'Ordner/Container',
        icons: [
            {id: 'bxs-folder', name: 'Ordner'},
            {id: 'bx-folder-open', name: 'Offener Ordner'},
            {id: 'bxs-archive', name: 'Archiv'},
        ],
    },
    {
        title: 'Dokumente/Notizen',
        icons: [
            {id: 'bxs-file-doc', name: 'Dokument'},
            {id: 'bxs-note', name: 'Notiz'},
            {id: 'bx-code-block', name: 'Code-Block'},
        ],
    },
    {
        title: 'Konzepte/Ideen',
        icons: [
            {id: 'bxs-bulb', name: 'Idee'},
            {id: 'bxs-brain', name: 'Konzept'},
            {id: 'bx-sitemap', name: 'Sitemap'},
        ],
    },
    {
        title: 'Personen/Teams',
        icons: [
            {id: 'bxs-user-detail', name: 'Person'},
            {id: 'bxs-group', name: 'Team'},
        ],
    },
    {
        title: 'Listen/Aufgaben',
        icons: [
            {id: 'bx-list-ul', name: 'Liste'},
            {id: 'bx-check-square', name: 'Aufgabe'},
        ],
    },
];

export default function IconSelectorDropdown({ currentVersion, vaultId, nodeId }) {
    const queryClient = useQueryClient(); // NEU: QueryClient für die Invalidierung

    // NEU: Mutation für die Icon-Änderung
    const changeIconMutation = useMutation({
        mutationFn: (payload) => {
            // Die Mutation-Funktion führt den API-Aufruf aus.
            return apiClient.patch(`/api/vaults/${vaultId}/nodes/${nodeId}/icon`, {
                icon: payload.iconId,
            });
        },
        onSuccess: () => {
            console.log("[MUTATION SUCCESS] Invalidating queries after icon change.");
            // Invalidiere beide Queries, in denen das Icon angezeigt wird.
            queryClient.invalidateQueries({ queryKey: ['vaultTree', vaultId] });
            queryClient.invalidateQueries({ queryKey: ['versions', vaultId, nodeId] });
        },
        onError: (error) => {
            console.error("Fehler beim Ändern des Icons:", error);
            // Optional: Hier könnte man den Optimistic Update zurückrollen, falls implementiert.
        }
    });

    if (!currentVersion) return null;

    const handleIconSelect = (iconId) => {
        if (iconId === currentVersion.icon || changeIconMutation.isPending) {
            return; // Verhindere Klicks während eine Änderung läuft
        }

        // Rufe die Mutation mit dem neuen Icon auf.
        changeIconMutation.mutate({ iconId });
    };

    // Wir können das Icon, das gesendet wird, für ein "Optimistic Update" verwenden.
    // `variables` enthält das, was an `mutate()` übergeben wurde.
    const displayIcon = changeIconMutation.isPending
        ? changeIconMutation.variables.iconId
        : currentVersion.icon;

    return (
        <Dropdown>
            <Dropdown.Toggle
                variant="light"
                size="sm"
                id="icon-selector-dropdown"
                title="Icon ändern"
                className="d-flex align-items-center"
                disabled={changeIconMutation.isPending} // Deaktiviere den Button während des Ladens
            >
                <i className={`bx ${displayIcon} fs-5`}></i>
            </Dropdown.Toggle>

            <Dropdown.Menu align="end" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                {iconGroups.map((group, groupIndex) => (
                    <React.Fragment key={group.title}>
                        {groupIndex > 0 && <Dropdown.Divider />}
                        <Dropdown.Header>{group.title}</Dropdown.Header>
                        {group.icons.map((icon) => (
                            <Dropdown.Item
                                key={icon.id}
                                onClick={() => handleIconSelect(icon.id)}
                                active={currentVersion.icon === icon.id}
                            >
                                <i className={`bx ${icon.id} me-2`}></i>
                                {icon.name}
                            </Dropdown.Item>
                        ))}
                    </React.Fragment>
                ))}
            </Dropdown.Menu>
        </Dropdown>
    );
}