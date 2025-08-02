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

export default function IconSelectorDropdown({currentNode, vaultId}) {
    const fetcher = useFetcher();
    const revalidator = useRevalidator();

    // 1. Ein Ref erstellen, um den vorherigen Zustand des Fetchers zu speichern
    const prevFetcherState = useRef(fetcher.state);

    useEffect(() => {
        // 2. Die Bedingung anpassen: Wir handeln nur, wenn der Zustand sich geändert hat!
        // Wir wollen den Moment abfangen, in dem der Fetcher von "submitting" zu "idle" wechselt.
        if (
            prevFetcherState.current === 'submitting' &&
            fetcher.state === 'idle' &&
            fetcher.data?.ok
        ) {
            console.log('Icon-Änderung abgeschlossen, revalidiere Baum...');
            revalidator.revalidate();
        }

        // 3. Den aktuellen Zustand für den nächsten Durchlauf im Ref speichern.
        // Dies muss NACH der Prüfung geschehen.
        prevFetcherState.current = fetcher.state;

    }, [fetcher.state, fetcher.data, revalidator]);


    if (!currentNode) {
        return null;
    }

    const handleIconSelect = (iconId) => {
        fetcher.submit(
            {intent: 'changeIcon', icon: iconId},
            {
                method: 'POST',
                action: `/vaults/${vaultId}/nodes/${currentNode.id}`,
            }
        );
    };

    return (
        <Dropdown>
            <Dropdown.Toggle
                variant="light"
                size="sm"
                id="icon-selector-dropdown"
                title="Icon ändern"
                className="d-flex align-items-center"
            >
                <i className={`bx ${fetcher.formData?.get('icon') || currentNode.icon} fs-5`}></i>
            </Dropdown.Toggle>

            <Dropdown.Menu align="end" style={{maxHeight: '300px', overflowY: 'auto'}}>
                {iconGroups.map((group, groupIndex) => (
                    <React.Fragment key={group.title}>
                        {groupIndex > 0 && <Dropdown.Divider/>}
                        <Dropdown.Header>{group.title}</Dropdown.Header>
                        {group.icons.map((icon) => (
                            <Dropdown.Item
                                key={icon.id}
                                onClick={() => handleIconSelect(icon.id)}
                                active={currentNode.icon === icon.id}
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