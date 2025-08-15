import React from 'react';
import { ListGroup, Button, Alert, Spinner } from 'react-bootstrap';
import { BsArrowLeftRight } from 'react-icons/bs';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import apiClient from '../../api/apiClient.js';
import { useWorkspaceStore } from '../workspace/workspaceStore.js';
import './VersionHistoryTab.css'; // Stelle sicher, dass diese CSS-Datei existiert und importiert wird

export default function VersionHistoryTab() {
    const navigate = useNavigate();
    const { vaultId, nodeId } = useParams();
    const { setDiffBase, setDiffCompare } = useWorkspaceStore();
    const diffSelection = useWorkspaceStore(state => state.diffSelection);

    const { data: versions, isLoading, isError, error } = useQuery({
        queryKey: ['versions', vaultId, nodeId],
        queryFn: async () => {
            if (!nodeId) return [];
            const response = await apiClient.get(`/api/vaults/${vaultId}/nodes/${nodeId}/versions`);
            return response.data || [];
        },
        enabled: !!vaultId && !!nodeId,
    });

    // ==========================================================
    // HANDLER-FUNKTIONEN
    // ==========================================================

    const updateUrl = (params) => {
        // Use an empty string for the path to only update search params
        navigate({ search: params.toString() }, { replace: true });
    };

    const handleSelectVersion = (version) => {
        setDiffBase(version);
        const newSearchParams = new URLSearchParams(window.location.search); // Preserve other params
        newSearchParams.set('version', String(version.version));
        updateUrl(newSearchParams);
    };

    const handleCompareVersion = (versionToCompare) => {
        const newSearchParams = new URLSearchParams(window.location.search);
        const isCurrentlyComparing = diffSelection.compare?.id === versionToCompare.id;

        if (isCurrentlyComparing) {
            // AKTION: "Vergleich beenden"
            // 1. Setze nur den Vergleichszustand auf null. Der `base` Zustand
            //    bleibt unberührt, sodass die Ansicht zur ausgewählten Basisversion zurückkehrt.
            setDiffCompare(null);

            // 2. Entferne NUR den `compare`-Parameter aus der URL.
            //    Der `version`-Parameter (für die Basisversion) bleibt erhalten.
            newSearchParams.delete('compare');
            updateUrl(newSearchParams);
        } else {
            // AKTION: "Vergleich starten" (Diese Logik war bereits korrekt)
            setDiffCompare(versionToCompare);
            newSearchParams.set('compare', String(versionToCompare.version));
            updateUrl(newSearchParams);
        }
    };

    const handleShowCurrent = () => {
        if (versions && versions.length > 0) {
            setDiffBase(versions[0]);
            // Wichtig: Auch den Vergleichszustand zurücksetzen, falls einer aktiv war.
            setDiffCompare(null);
            updateUrl(new URLSearchParams());
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
                            <ListGroup.Item
                                key={v.id}
                                active={isBase}
                                className={`d-flex justify-content-between align-items-center version-list-item ${isCompare ? 'diff-compare-active' : ''}`}
                            >
                                <div className="flex-grow-1 me-2" style={{ minWidth: 0, cursor: 'pointer' }} onClick={() => handleSelectVersion(v)}>
                                    <strong className="d-block text-truncate" title={v.title || `Version ${v.version}`}>{v.title || `Version ${v.version}`}</strong>
                                    <small className="text-muted">v{v.version} von {v.author_name || 'N/A'}</small><br/>
                                    <small className="text-muted">{new Date(v.timestamp).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}</small>
                                </div>
                                {showDiffButton && (
                                    <Button
                                        variant="outline-info"
                                        size="sm"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleCompareVersion(v);
                                            e.currentTarget.blur();
                                        }}
                                        title={isCompare ? "Vergleich aufheben" : `Vergleiche mit v${base?.version}`}
                                        // Der 'active' Zustand wird jetzt implizit durch die 'diff-compare-active' Klasse gesteuert.
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