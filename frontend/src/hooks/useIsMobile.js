// src/hooks/useIsMobile.js
import { useState, useEffect } from 'react';

// Der Breakpoint, ab dem wir als "mobil" gelten (Bootstrap 'lg' ist 992px)
const MOBILE_BREAKPOINT = 992;

export const useIsMobile = () => {
    const [isMobile, setIsMobile] = useState(window.innerWidth < MOBILE_BREAKPOINT);

    useEffect(() => {
        const handleResize = () => {
            setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
        };

        window.addEventListener('resize', handleResize);

        // Cleanup-Funktion: Entfernt den Listener, wenn die Komponente unmounted wird
        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, []); // Leeres Array bedeutet, dass der Effekt nur bei Mount/Unmount ausgeführt wird

    return isMobile;
};