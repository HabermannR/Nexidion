import React from 'react';
import { ListGroup, Button, Alert, Spinner } from 'react-bootstrap';
import { BsArrowLeftRight } from 'react-icons/bs';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams, useParams } from 'react-router-dom';
import apiClient from '../../../api/apiClient';
import { useWorkspaceStore } from '../workspaceStore.js';
import './VersionHistoryTab.css'; // Stelle sicher, dass diese CSS-Datei existiert und importiert wird

export default function VersionHistoryTab() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { vaultId, nodeId } = useParams();
    const { setDiffBase, setDiffCompare } = useWorkspaceStore();
    const diffSelection = useWorkspaceStore(state => state.diffSelection);

    // ==========================================================
    // SÄULE 2: DIE DATEN-ENGINE (TanStack Query)
    // Dieser Hook ersetzt den alten Loader-Mechanismus und den 'activeNodeVersions' Store.
    // ==========================================================
    const { data: versions, isLoading, isError, error } = useQuery({
        queryKey: ['versions', vaultId, nodeId],

        queryFn: async () => {
            // Die Logik hier war schon korrekt, aber der Key muss passen.
            if (!nodeId) return [];
            const response = await apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`);
            return response.data || [];
        },
        // Die enabled-Bedingung muss ebenfalls vaultId prüfen, um konsistent zu sein.
        enabled: !!vaultId && !!nodeId,
    });


    // ==========================================================
    // HANDLER-FUNKTIONEN
    // ==========================================================

    const updateUrl = (params) => {
        navigate(`?${params.toString()}`, { replace: true });
    };

    const handleSelectVersion = (version) => {
        setDiffBase(version); // 1. Store aktualisieren
        const newSearchParams = new URLSearchParams();
        newSearchParams.set('version', String(version.version));
        updateUrl(newSearchParams); // 2. URL aktualisieren
    };

    const handleCompareVersion = (version) => {
        const newSearchParams = new URLSearchParams(window.location.search);

        // Prüfen, ob diese Version bereits die Vergleichsversion ist.
        if (newSearchParams.get('compare') === String(version.version)) {
            // Ja -> Vergleich aufheben
            newSearchParams.delete('compare');
            setDiffCompare(null); // Zustand zurücksetzen!
        } else {
            // Nein -> Als neue Vergleichsversion setzen
            newSearchParams.set('compare', String(version.version));
            setDiffCompare(version); // Zustand setzen!
        }

        updateUrl(newSearchParams); // URL am Ende aktualisieren
    };

    const handleShowCurrent = () => {
        if (versions && versions.length > 0) {
            setDiffBase(versions[0]); // 1. Store auf die neueste Version setzen
            const newSearchParams = new URLSearchParams();
            updateUrl(newSearchParams); // 2. URL aufräumen
        }
    };

    // ==========================================================
    // RENDER-LOGIK MIT ROBUSTEN ZUSTÄNDEN
    // ==========================================================

    if (!nodeId) {
        return <Alert variant="secondary" className="m-3 small">Kein Dokument ausgewählt.</Alert>;
    }

    if (isLoading) {
        return (
            <div className="d-flex justify-content-center align-items-center h-100">
                <Spinner animation="border" role="status">
                    <span className="visually-hidden">Lade Versionen...</span>
                </Spinner>
            </div>
        );
    }

    if (isError) {
        return <Alert variant="danger" className="m-3 small">Fehler beim Laden: {error.message}</Alert>;
    }

    if (!versions || versions.length === 0) {
        return <Alert variant="info" className="m-3 small">Keine früheren Versionen für dieses Dokument vorhanden.</Alert>;
    }

    // Sicherstellen, dass die App nicht abstürzt, wenn diffSelection anfangs undefined ist.
    const { base, compare } = diffSelection || {};
    const latestVersion = versions?.[0];

    return (
        <div className="version-history-container">
            {base && latestVersion && base.id !== latestVersion.id && (
                <div className="px-1 pb-2 flex-shrink-0">
                    <Button variant="outline-secondary" size="sm" className="w-100" onClick={handleShowCurrent}>
                        Zurück zur aktuellen Version
                    </Button>
                </div>
            )}
            <div className="version-list-scroll-area">
                <ListGroup variant="flush">
                    {versions.map(v => {
                        const isBase = base?.id === v.id;
                        const isCompare = compare?.id === v.id;
                        const showDiffButton = base && !isBase;

                        return (
                            <ListGroup.Item key={v.id} active={isBase} className={`d-flex justify-content-between align-items-center version-list-item ${isCompare ? 'diff-compare-active' : ''}`}>
                                <div className="flex-grow-1 me-2" style={{ minWidth: 0, cursor: 'pointer' }} onClick={() => handleSelectVersion(v)}>
                                    <strong className="d-block text-truncate" title={v.title || `Version ${v.version}`}>{v.title || `Version ${v.version}`}</strong>
                                    <small className="text-muted">v{v.version} von {v.author_name || 'N/A'}</small><br/>
                                    <small className="text-muted">{new Date(v.timestamp).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}</small>
                                </div>
                                {showDiffButton && (
                                    <Button
                                        // KORREKTUR: Immer 'outline-info' verwenden. Das CSS kümmert sich um den Rest.
                                        variant="outline-info"
                                        size="sm"
                                        // HINWEIS: Die Klasse 'btn-info' wird jetzt nicht mehr hinzugefügt,
                                        // was das Styling vereinfacht.
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleCompareVersion(v);
                                            // NEU: Dem Button nach dem Klick den Fokus entziehen.
                                            // Das ist eine robuste Methode, um "klebende" Hover/Focus-Stile zu verhindern.
                                            e.currentTarget.blur();
                                        }}
                                        title={isCompare ? "Vergleich aufheben" : `Vergleiche mit v${base?.version}`}
                                    >
                                        <BsArrowLeftRight />
                                    </Button>
                                )}
                            </ListGroup.Item>
                        );
                    })}
                </ListGroup>
            </div>
        </div>
    );
}