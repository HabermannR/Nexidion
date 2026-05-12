import React, { useCallback } from 'react';
import { ListGroup, Button, Alert, Spinner } from 'react-bootstrap';
import { BsArrowLeftRight, BsCloudDownload } from 'react-icons/bs';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import apiClient from '../../api/apiClient.js';
import './VersionHistoryTab.css';

// ---------------------------------------------------------------------------
// Sub-component: one version row (stub or full)
// ---------------------------------------------------------------------------
function VersionRow({ v, isBase, isCompare, showDiffButton, vaultId, nodeId, onSelect, onCompare }) {
    const queryClient = useQueryClient();

    // Prefetch full version on hover so the click feels instant
    const handleMouseEnter = useCallback(() => {
        queryClient.prefetchQuery({
            queryKey: ['nodeContent', vaultId, nodeId, String(v.version)],
            queryFn: async () => {
                const res = await apiClient.get(
                    `/api/vaults/${vaultId}/nodes/${nodeId}`, { params: { version: v.version } }
                );
                return res.data;
            },
            staleTime: Infinity,
        });
    }, [v.version, vaultId, nodeId, queryClient]);

    return (
        <ListGroup.Item
            active={isBase}
            className={`d-flex justify-content-between align-items-center version-list-item ${isCompare ? 'diff-compare-active' : ''}`}
            onMouseEnter={handleMouseEnter}
        >
            <div
                className="flex-grow-1 me-2"
                style={{ minWidth: 0, cursor: 'pointer' }}
                onClick={() => onSelect(v)}
            >
                <div className="d-flex align-items-center gap-1">
                    <strong className="text-truncate" title={v.title || `Version ${v.version}`}>
                        {v.title || `Version ${v.version}`}
                    </strong>
                    {v.is_stub && (
                        <BsCloudDownload
                            className="text-muted flex-shrink-0"
                            size={11}
                            title="Inhalt wird beim Anklicken geladen"
                        />
                    )}
                </div>
                <small className="text-muted">v{v.version} von {v.author_name || 'N/A'}</small>
                <br />
                <small className="text-muted">
                    {new Date(v.timestamp).toLocaleString('de-DE', {
                        dateStyle: 'short',
                        timeStyle: 'short',
                        timeZone: 'UTC',
                    })}
                </small>
            </div>
            {showDiffButton && (
                <Button
                    variant="outline-info"
                    size="sm"
                    onClick={(e) => {
                        e.stopPropagation();
                        onCompare(v);
                        e.currentTarget.blur();
                    }}
                    title={isCompare ? 'Vergleich aufheben' : `Vergleiche mit dieser Version`}
                >
                    <BsArrowLeftRight />
                </Button>
            )}
        </ListGroup.Item>
    );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function VersionHistoryTab() {
    const navigate = useNavigate();
    const { vaultId, nodeId } = useParams();
    const [searchParams] = useSearchParams();

    const baseVersionParam = searchParams.get('version');
    const compareVersionParam = searchParams.get('compare');

    // ---- Version list (purely lightweight metadata stubs now) ----
    const { data: versions, isLoading, isError, error } = useQuery({
        queryKey: ['versions', vaultId, nodeId],
        queryFn: async () => {
            if (!nodeId) return[];
            const response = await apiClient.get(
                `/api/vaults/${vaultId}/nodes/${nodeId}/versions`
            );
            return response.data ||[];
        },
        enabled: !!vaultId && !!nodeId,
    });

    const updateUrl = useCallback((params) => {
        navigate({ search: params.toString() }, { replace: true });
    }, [navigate]);

    const handleSelectVersion = useCallback(
        (v) => {
            const params = new URLSearchParams(searchParams);
            params.set('version', String(v.version));
            updateUrl(params);
        },
        [searchParams, updateUrl]
    );

    const handleCompareVersion = useCallback(
        (v) => {
            const params = new URLSearchParams(searchParams);
            const isCurrentlyComparing = compareVersionParam === String(v.version);

            if (isCurrentlyComparing) {
                params.delete('compare');
            } else {
                params.set('compare', String(v.version));
            }
            updateUrl(params);
        },
        [searchParams, compareVersionParam, updateUrl]
    );

    const handleShowCurrent = useCallback(() => {
        if (versions && versions.length > 0) {
            const params = new URLSearchParams(searchParams);
            params.delete('version');
            params.delete('compare');
            updateUrl(params);
        }
    }, [versions, searchParams, updateUrl]);

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
        return (
            <Alert variant="info" className="m-3 small">
                Keine früheren Versionen für dieses Dokument vorhanden.
            </Alert>
        );
    }

    const currentBaseStr = baseVersionParam || String(versions[0].version);
    const latestVersion = versions[0];
    const isShowingLatest = currentBaseStr === String(latestVersion.version);

    return (
        <div className="version-history-container">
            {!isShowingLatest && (
                <div className="px-1 pb-2 flex-shrink-0">
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        className="w-100"
                        onClick={handleShowCurrent}
                    >
                        Zurück zur aktuellen Version
                    </Button>
                </div>
            )}
            <div className="version-list-scroll-area">
                <ListGroup variant="flush">
                    {versions.map((v) => (
                        <VersionRow
                            key={v.id}
                            v={v}
                            isBase={currentBaseStr === String(v.version)}
                            isCompare={compareVersionParam === String(v.version)}
                            showDiffButton={currentBaseStr !== String(v.version)}
                            vaultId={vaultId}
                            nodeId={nodeId}
                            onSelect={handleSelectVersion}
                            onCompare={handleCompareVersion}
                        />
                    ))}
                </ListGroup>
            </div>
        </div>
    );
}