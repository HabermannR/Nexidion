// src/features/nodes/ui/IconSelectorDropdown.jsx (KORRIGIERT)

import React from 'react';
import { Dropdown } from 'react-bootstrap';
import { useMutation, useQueryClient } from '@tanstack/react-query'; // NEU
import apiClient from '../../api/apiClient.js'; // NEU

// Datenstruktur für die Icons, gruppiert nach Kategorien
const iconGroups = [
    {
        title: 'Folders & Containers',
        icons: [
            {id: 'bxs-folder', name: 'Folder'},
            {id: 'bx-folder-open', name: 'Open Folder'},
            {id: 'bxs-inbox', name: 'Inbox'},
            {id: 'bxs-archive', name: 'Archive'},
            {id: 'bxs-box', name: 'Collection'}, // For generic collections
            {id: 'bxs-component', name: 'Component'}, // For reusable content
        ],
    },
    {
        title: 'Documents & Notes',
        icons: [
            {id: 'bxs-file-doc', name: 'Document'},
            {id: 'bxs-note', name: 'Note'},
            {id: 'bx-code-block', name: 'Code'},
            {id: 'bxs-file-pdf', name: 'PDF'},
            {id: 'bxs-copy-alt', name: 'Template'},
            {id: 'bxs-edit-alt', name: 'Draft'}, // For documents in progress
        ],
    },
    {
        title: 'Concepts & Planning',
        icons: [
            {id: 'bxs-bulb', name: 'Idea'},
            {id: 'bxs-brain', name: 'Concept'},
            {id: 'bx-sitemap', name: 'Structure'},
            {id: 'bxs-bullseye', name: 'Goal'},
            {id: 'bxs-flag-alt', name: 'Milestone'},
            {id: 'bxs-network-chart', name: 'Relationships'}, // To represent connections
        ],
    },
    {
        title: 'People & Teams',
        icons: [
            {id: 'bxs-user', name: 'Person'},
            {id: 'bxs-group', name: 'Team'},
            {id: 'bxs-contact', name: 'Contact'},
            {id: 'bxs-user-detail', name: 'Profile'},
            {id: 'bxs-user-voice', name: 'Feedback'},
            {id: 'bxs-user-plus', name: 'Add User'},
        ],
    },
    {
        title: 'Lists & Tasks',
        icons: [
            {id: 'bx-list-ul', name: 'List'},
            {id: 'bx-check-square', name: 'Task'},
            {id: 'bxs-hourglass-top', name: 'In Progress'},
            {id: 'bxs-calendar', name: 'Appointment'},
            {id: 'bxs-time-five', name: 'Deadline'},
            {id: 'bxs-calendar-check', name: 'Completed'},
            {id: 'bxs-calendar-x', name: 'Missed'},
        ],
    },
    {
        title: 'Structure & Metadata',
        icons: [
            {id: 'bxs-tag-alt', name: 'Tag'},
            {id: 'bx-link', name: 'Link'},
            {id: 'bx-link-external', name: 'External Link'},
            {id: 'bxs-pin', name: 'Pinned'},
            {id: 'bxs-star', name: 'Favorite'},
            {id: 'bxs-bookmark', name: 'Bookmark'},
            {id: 'bxs-bookmark-star', name: 'Favorite Bookmark'}, // Name slightly shortened
        ],
    },
    {
        title: 'Media & Attachments',
        icons: [
            {id: 'bxs-image-alt', name: 'Image'},
            {id: 'bxs-video', name: 'Video'},
            {id: 'bxs-music', name: 'Audio'},
            {id: 'bxs-file-archive', name: 'ZIP Archive'},
            {id: 'bxs-cloud-upload', name: 'Upload'},
            {id: 'bxs-file-find', name: 'File Search'}, // Better name for the icon
        ],
    },
    {
        title: 'Data & Visualization',
        icons: [
            {id: 'bx-table', name: 'Table'},
            {id: 'bxs-bar-chart-alt-2', name: 'Bar Chart'},
            {id: 'bxs-pie-chart-alt-2', name: 'Pie Chart'},
            {id: 'bxs-data', name: 'Data Source'},
            {id: 'bxs-map', name: 'Map'},
            {id: 'bxs-map-pin', name: 'Location'},
        ],
    },
    {
        title: 'Status & Communication',
        icons: [
            {id: 'bxs-info-circle', name: 'Info'},
            {id: 'bxs-help-circle', name: 'Question'},
            {id: 'bxs-error-circle', name: 'Warning'},
            {id: 'bxs-check-circle', name: 'Confirmed'},
            {id: 'bxs-comment-detail', name: 'Discussion'},
            {id: 'bxs-bell', name: 'Notification'},
            {id: 'bxs-lock-alt', name: 'Locked '},
            {id: 'bxs-no-entry', name: 'Private'},
            {id: 'bx-trash', name: 'Trash'},
        ],
    },
];

export default function IconSelectorDropdown({ currentVersion, vaultId, nodeId, disabled = false }) {
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
        if (disabled || iconId === currentVersion.icon || changeIconMutation.isPending) {
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
                disabled={disabled || changeIconMutation.isPending}
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
