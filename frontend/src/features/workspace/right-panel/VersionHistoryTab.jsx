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

    // ==========================================================
    // SÄULE 2: DIE DATEN-ENGINE (TanStack Query)
    // Dieser Hook ersetzt den alten Loader-Mechanismus und den 'activeNodeVersions' Store.
    // ==========================================================
    const { data: versions, isLoading, isError, error } = useQuery({
        queryKey: ['versions', nodeId],
        queryFn: async () => {
            if (!nodeId) return []; // Führe keinen API-Call ohne nodeId aus
            console.log(`[useQuery] Fetching versions for node: ${nodeId}`);
            const response = await apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`);
            return response.data || [];
        },
        // Der Query wird nur aktiviert, wenn eine nodeId in der URL vorhanden ist.
        enabled: !!nodeId,
    });

    // ==========================================================
    // SÄULE 3: DER UI-CONTROLLER (Zustand)
    // 'diffSelection' ist reiner Client-Zustand und bleibt in Zustand.
    // ==========================================================
    const diffSelection = useWorkspaceStore(state => state.diffSelection);

    // ==========================================================
    // HANDLER-FUNKTIONEN
    // ==========================================================

    const handleSelectVersion = (version) => {
        const newSearchParams = new URLSearchParams(searchParams);
        newSearchParams.set('version', String(version.version));
        newSearchParams.delete('compare');
        navigate(`?${newSearchParams.toString()}`, { replace: true });
    };

    const handleCompareVersion = (version) => {
        const newSearchParams = new URLSearchParams(searchParams);
        if (newSearchParams.get('compare') === String(version.version)) {
            newSearchParams.delete('compare');
        } else {
            newSearchParams.set('compare', String(version.version));
        }
        navigate(`?${newSearchParams.toString()}`, { replace: true });
    };

    const handleShowCurrent = () => {
        const newSearchParams = new URLSearchParams(searchParams);
        newSearchParams.delete('version');
        newSearchParams.delete('compare');
        navigate(`?${newSearchParams.toString()}`, { replace: true });
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
                                    <Button variant={isCompare ? "info" : "outline-info"} size="sm" onClick={(e) => { e.stopPropagation(); handleCompareVersion(v); }} title={isCompare ? "Vergleich aufheben" : `Vergleiche mit v${base?.version}`}>
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