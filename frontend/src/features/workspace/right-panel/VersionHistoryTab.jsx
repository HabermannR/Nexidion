// src/features/workspace/right-panel/VersionHistoryTab.jsx

import React from 'react';
import { ListGroup, Button, Alert } from 'react-bootstrap';
import { BsArrowLeftRight } from 'react-icons/bs';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './VersionHistoryTab.css';
import { useWorkspaceStore } from '../workspaceStore.js';

export default function VersionHistoryTab() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    // ==========================================================
    // --- KORREKTUR: Stabile Selektoren ---
    // Wir rufen den Hook jetzt für jeden Wert einzeln auf.
    // Das stellt sicher, dass die Komponente nur neu rendert, wenn sich
    // die jeweiligen Daten im Store auch wirklich ändern.
    // KEINE NEUEN OBJEKTE MEHR BEI JEDEM RENDER!
    // ==========================================================
    const versions = useWorkspaceStore(state => state.activeNodeVersions);
    const diffSelection = useWorkspaceStore(state => state.diffSelection);

    // Die restliche Logik kann unverändert bleiben, da sie auf korrekten
    // und jetzt stabilen Daten operiert.
    const latestVersion = versions?.[0];

    // --- KEIN useEffect mehr nötig. Die Komponente ist jetzt rein reaktiv. ---

    const handleSelectVersion = (version) => {
        const newSearchParams = new URLSearchParams(searchParams);
        newSearchParams.set('version', version.version);
        newSearchParams.delete('compare');
        navigate(`?${newSearchParams.toString()}`, { replace: true });
    };

    const handleCompareVersion = (version) => {
        const newSearchParams = new URLSearchParams(searchParams);
        if (newSearchParams.get('compare') === String(version.version)) {
            newSearchParams.delete('compare');
        } else {
            newSearchParams.set('compare', version.version);
        }
        navigate(`?${newSearchParams.toString()}`, { replace: true });
    };

    const handleShowCurrent = () => {
        navigate('.', { replace: true });
    };

    if (!versions || versions.length === 0) {
        return <Alert variant="info" className="mx-3 mt-3 small">Keine früheren Versionen für dieses Dokument vorhanden.</Alert>;
    }

    const { base, compare } = diffSelection;

    return (
        <div className="d-flex flex-column h-100">
            {base && latestVersion && base.id !== latestVersion.id && (
                <div className="px-3 pt-3">
                    <Button variant="outline-secondary" size="sm" className="w-100" onClick={handleShowCurrent}>
                        Zurück zur aktuellen Version
                    </Button>
                </div>
            )}
            <ListGroup variant="flush" className="mt-2">
                {versions.map(v => {
                    const isBase = base?.id === v.id;
                    const isCompare = compare?.id === v.id;
                    const showDiffButton = base && !isBase;

                    return (
                        <ListGroup.Item key={v.id} active={isBase} className={`d-flex justify-content-between align-items-center version-list-item ${isCompare ? 'diff-compare-active' : ''}`}>
                            <div className="flex-grow-1 me-2" style={{ minWidth: 0, cursor: 'pointer' }} onClick={() => handleSelectVersion(v)}>
                                <strong className="d-block text-truncate" title={v.title}>{v.title || `Version ${v.version}`}</strong>
                                <small className="text-muted">v{v.version} von {v.author_name}</small><br/>
                                <small className="text-muted">{new Date(v.timestamp).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}</small>
                            </div>
                            {showDiffButton && (
                                <Button variant={isCompare ? "info" : "outline-info"} size="sm" onClick={(e) => { e.stopPropagation(); handleCompareVersion(v); }} title={isCompare ? "Vergleich aufheben" : `Vergleiche mit v${base.version}`}>
                                    <BsArrowLeftRight />
                                </Button>
                            )}
                        </ListGroup.Item>
                    );
                })}
            </ListGroup>
        </div>
    );
}