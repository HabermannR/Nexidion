// src/features/nodes/ui/IconSelectorDropdown.jsx (KORRIGIERT)

import React from 'react';
import { Dropdown } from 'react-bootstrap';
import { useMutation, useQueryClient } from '@tanstack/react-query'; // NEU
import apiClient from '../../../api/apiClient'; // NEU

// Datenstruktur für die Icons, gruppiert nach Kategorien
const iconGroups = [
    {
        title: 'Ordner & Container',
        icons: [
            {id: 'bxs-folder', name: 'Ordner'},
            {id: 'bx-folder-open', name: 'Offener Ordner'},
            {id: 'bxs-inbox', name: 'Eingang'},
            {id: 'bxs-archive', name: 'Archiv'},
            {id: 'bxs-box', name: 'Sammlung'}, // Für generische Sammlungen
            {id: 'bxs-component', name: 'Baustein'}, // Für wiederverwendbare Inhalte
        ],
    },
    {
        title: 'Dokumente & Notizen',
        icons: [
            {id: 'bxs-file-doc', name: 'Dokument'},
            {id: 'bxs-note', name: 'Notiz'},
            {id: 'bx-code-block', name: 'Code'},
            {id: 'bxs-file-pdf', name: 'PDF'},
            {id: 'bxs-copy-alt', name: 'Vorlage'},
            {id: 'bxs-edit-alt', name: 'Entwurf'}, // Für Dokumente in Arbeit
        ],
    },
    {
        title: 'Konzepte & Planung',
        icons: [
            {id: 'bxs-bulb', name: 'Idee'},
            {id: 'bxs-brain', name: 'Konzept'},
            {id: 'bx-sitemap', name: 'Struktur'},
            {id: 'bxs-bullseye', name: 'Ziel'},
            {id: 'bxs-flag-alt', name: 'Meilenstein'},
            {id: 'bxs-network-chart', name: 'Beziehungen'}, // Um Verknüpfungen darzustellen
        ],
    },
    {
        title: 'Personen & Teams',
        icons: [
            {id: 'bxs-user', name: 'Person'},
            {id: 'bxs-group', name: 'Team'},
            {id: 'bxs-contact', name: 'Kontakt'},
            {id: 'bxs-user-detail', name: 'Profil'},
            {id: 'bxs-user-voice', name: 'Feedback'},
            {id: 'bxs-user-plus', name: 'Benutzer hinzufügen'},
        ],
    },
    {
        title: 'Listen & Aufgaben',
        icons: [
            {id: 'bx-list-ul', name: 'Liste'},
            {id: 'bx-check-square', name: 'Aufgabe'},
            {id: 'bxs-hourglass-top', name: 'In Bearbeitung'},
            {id: 'bxs-calendar', name: 'Termin'},
            {id: 'bxs-time-five', name: 'Frist'},
            {id: 'bxs-calendar-check', name: 'Abgeschlossen'},
            {id: 'bxs-calendar-x', name: 'Verpasst'},
        ],
    },
    {
        title: 'Struktur & Metadaten',
        icons: [
            {id: 'bxs-tag-alt', name: 'Schlagwort'},
            {id: 'bx-link', name: 'Link'},
            {id: 'bx-link-external', name: 'Externer Link'},
            {id: 'bxs-pin', name: 'Angepinnt'},
            {id: 'bxs-star', name: 'Favorit'},
            {id: 'bxs-bookmark', name: 'Lesezeichen'},
            {id: 'bxs-bookmark-star', name: 'Favoriten-Lesezeichen'}, // Name leicht gekürzt
        ],
    },
    {
        title: 'Medien & Anhänge',
        icons: [
            {id: 'bxs-image-alt', name: 'Bild'},
            {id: 'bxs-video', name: 'Video'},
            {id: 'bxs-music', name: 'Audio'},
            {id: 'bxs-file-archive', name: 'ZIP-Archiv'},
            {id: 'bxs-cloud-upload', name: 'Upload'},
            {id: 'bxs-file-find', name: 'Dateisuche'}, // Besserer Name für das Icon
        ],
    },
    {
        title: 'Daten & Visualisierung',
        icons: [
            {id: 'bx-table', name: 'Tabelle'},
            {id: 'bxs-bar-chart-alt-2', name: 'Balkendiagramm'},
            {id: 'bxs-pie-chart-alt-2', name: 'Kreisdiagramm'},
            {id: 'bxs-data', name: 'Datenquelle'},
            {id: 'bxs-map', name: 'Karte'},
            {id: 'bxs-map-pin', name: 'Ort'},
        ],
    },
    {
        title: 'Status & Kommunikation',
        icons: [
            {id: 'bxs-info-circle', name: 'Info'},
            {id: 'bxs-help-circle', name: 'Frage'},
            {id: 'bxs-error-circle', name: 'Warnung'},
            {id: 'bxs-check-circle', name: 'Bestätigt'},
            {id: 'bxs-comment-detail', name: 'Diskussion'},
            {id: 'bxs-bell', name: 'Benachrichtigung'},
            {id: 'bxs-lock-alt', name: 'Gesperrt / Privat'},
            {id: 'bx-trash', name: 'Papierkorb'},
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
                size="sm"
                id="icon-selector-dropdown"
                title="Icon ändern"
                className="d-flex align-items-center icon-selector-toggle"
                disabled={changeIconMutation.isPending}
            >
                {/* Das Haupt-Icon */}
                <i className={`bx ${displayIcon} fs-5`}></i>

                {/* NEU: Ein Chevron-Icon als Dropdown-Indikator */}
                <i className='bx bx-chevron-down ms-1'></i>

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