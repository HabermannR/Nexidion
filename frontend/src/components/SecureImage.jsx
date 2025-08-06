// IN: src/components/SecureImage.jsx (oder wo immer du sie ablegst)

import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/apiClient'; // Stelle sicher, dass der Pfad korrekt ist

export default function SecureImage({ src, alt, ...props }) {
    // ==========================================================
    // SÄULE 2: DATENLADUNG MIT useQuery
    // ==========================================================
    const { data: imageObjectUrl, isLoading, isError, error } = useQuery({
        // Der queryKey MUSS den `src`-Pfad enthalten, damit jede Bild-URL
        // einen eigenen, eindeutigen Cache-Eintrag erhält.
        queryKey: ['secureImage', src],

        queryFn: async () => {
            // Führe die Anfrage nur aus, wenn ein `src`-Pfad vorhanden ist.
            if (!src) return null;

            // Lade das Bild als Blob (binäre Daten).
            const response = await apiClient.get(src, { responseType: 'blob' });

            // Erstelle eine temporäre URL für den Blob, die der Browser anzeigen kann.
            return URL.createObjectURL(response.data);
        },

        // Wichtige Optionen für Bild-Caching:
        enabled: !!src, // Der Query wird nur ausgeführt, wenn `src` ein gültiger String ist.
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
        return () => {
            if (imageObjectUrl) {
                URL.revokeObjectURL(imageObjectUrl);
            }
        };
    }, [imageObjectUrl]);


    // ==========================================================
    // RENDER-LOGIK
    // ==========================================================

    // Fall 1: Fehler beim Laden
    if (isError) {
        console.error(`Failed to load secure image from ${src}:`, error);
        return <span className="image-error" {...props}>{alt || 'Image failed to load'}</span>;
    }

    // Fall 2: Bild wird gerade geladen
    if (isLoading) {
        return <span className="image-loading" {...props}>{alt || 'Loading image...'}</span>;
    }

    // Fall 3: Erfolgreich geladen
    return <img src={imageObjectUrl} alt={alt} {...props} />;
}