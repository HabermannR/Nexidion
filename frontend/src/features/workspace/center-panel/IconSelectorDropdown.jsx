// src/features/nodes/ui/IconSelectorDropdown.jsx (KORRIGIERT)

import React, {useEffect, useRef} from 'react';
import {Dropdown} from 'react-bootstrap';
import {useFetcher, useRevalidator} from 'react-router-dom';

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

// Wichtig: nodeId wird jetzt explizit übergeben.
export default function IconSelectorDropdown({ currentVersion, vaultId, nodeId }) {
    const fetcher = useFetcher();

    useEffect(() => {
        console.log(`[ICON FETCHER] Zustand: ${fetcher.state}, Daten:`, fetcher.data);
    }, [fetcher.state, fetcher.data]);

    if (!currentVersion) return null;

    const handleIconSelect = (iconId) => {
        console.log(`[ICON SELECTOR] Klick registriert. iconId: '${iconId}', vaultId: '${vaultId}', nodeId: '${nodeId}'`);
        if (iconId === currentVersion.icon) return;

        fetcher.submit(
            { intent: 'changeIcon', icon: iconId },
            {
                method: 'post',
                // Explizit die Action-URL angeben ist am robustesten.
                action: `/vaults/${vaultId}/nodes/${nodeId}`,
            }
        );
    };

    // Optimistic Update: Zeige das Icon an, das gerade gesendet wird, oder das aktuelle.
    const displayIcon = fetcher.formData?.get('icon') || currentVersion.icon;

    return (
        <Dropdown>
            <Dropdown.Toggle variant="light" size="sm" id="icon-selector-dropdown" title="Icon ändern" className="d-flex align-items-center">
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