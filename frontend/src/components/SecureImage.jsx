// IN: src/components/SecureImage.jsx (oder wo immer du sie ablegst)

import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/apiClient'; // Stelle sicher, dass der Pfad korrekt ist

export default function SecureImage({ src, alt, ...props }) {
    const isManagedAsset = /^\/api\/vaults\/\d+\/assets\/[0-9a-f-]{36}$/i.test(src || '');
    // ==========================================================
    // SÄULE 2: DATENLADUNG MIT useQuery
    // ==========================================================
    const [imageUrl, setImageUrl] = useState(null);
    const { data: imageBlob, isLoading, isError, error } = useQuery({
        // Der queryKey MUSS den `src`-Pfad enthalten, damit jede Bild-URL
        // einen eigenen, eindeutigen Cache-Eintrag erhält.
        queryKey: ['secureImage', src],

        queryFn: async () => {
            // Führe die Anfrage nur aus, wenn ein `src`-Pfad vorhanden ist.
            if (!isManagedAsset) throw new Error('Blocked non-managed image URL.');

            // Lade das Bild als Blob (binäre Daten).
            const response = await apiClient.get(src, { responseType: 'blob' });

            // Cache the Blob, not a URL that becomes invalid when a viewer unmounts.
            return response.data;
        },

        // Wichtige Optionen für Bild-Caching:
        enabled: !!src && isManagedAsset,
        staleTime: 1000 * 60 * 60, // 1 Stunde: Bilder ändern sich selten, aggressives Caching ist gut.
        gcTime: 1000 * 60 * 60,    // Garbage Collection Time ebenfalls hoch ansetzen.
        refetchOnWindowFocus: false, // Es ist unnötig, Bilder bei jedem Fenster-Fokus neu zu laden.
    });

    // ==========================================================
    // Nebeneffekt für den Cleanup
    // ==========================================================
    // Dieser `useEffect` ist der einzige, den wir noch brauchen. Er ist dafür
    // verantwortlich, die temporäre Blob-URL freizugeben, wenn die Komponente
    // verschwindet, um Speicherlecks zu verhindern.
    useEffect(() => {
        if (!imageBlob) return;
        const url = URL.createObjectURL(imageBlob);
        setImageUrl({ blob: imageBlob, url });
        return () => {
            URL.revokeObjectURL(url);
        };
    }, [imageBlob]);


    // ==========================================================
    // RENDER-LOGIK
    // ==========================================================

    if (!isManagedAsset) {
        return <span className="image-error" {...props}>{alt || 'External image blocked'}</span>;
    }

    // Fall 1: Fehler beim Laden
    if (isError) {
        console.error(`Failed to load secure image from ${src}:`, error);
        return <span className="image-error" {...props}>{alt || 'Image failed to load'}</span>;
    }

    // Fall 2: Bild wird gerade geladen
    if (isLoading || !imageUrl || imageUrl.blob !== imageBlob) {
        return <span className="image-loading" {...props}>{alt || 'Loading image...'}</span>;
    }

    // Fall 3: Erfolgreich geladen
    return <img src={imageUrl.url} alt={alt} {...props} />;
}
