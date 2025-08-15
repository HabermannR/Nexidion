import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useInternalLinkNavigation } from './hooks/useInternalLinkNavigation'; // Pfad anpassen!

/**
 * @param {string} target - Das Link-Ziel (Titel oder UUID).
 * @param {React.ReactNode} children - Der Inhalt des Links, von ReactMarkdown gerendert.
 */
// Wir nehmen wieder `displayText` anstatt `children`
export default function InternalLink({ uuid, targetTitle, displayText, className }) {
    const navigate = useNavigate();
    const { vaultId } = useParams();
    const { navigateToTitle } = useInternalLinkNavigation();

    const handleClick = (e) => {
        e.preventDefault();
        e.stopPropagation();

        // --- HIER FINDET DIE WEICHENSTELLUNG STATT ---

        if (uuid) {
            // STARKER LINK: Wir haben eine UUID, also navigieren wir direkt.
            // Kein API-Aufruf, keine Verzögerung.
            console.log(`Starker Link: Navigiere direkt zu UUID ${uuid}`);
            navigate(`/vaults/${vaultId}/nodes/${uuid}`);
        } else if (targetTitle) {
            // SCHWACHER LINK: Wir haben nur einen Titel, also rufen wir den Hook auf,
            // der die API-Anfrage zur Auflösung startet.
            console.log(`Schwacher Link: Löse Titel "${targetTitle}" auf...`);
            navigateToTitle(targetTitle);
        }
    };

    return (
        <a href="#" onClick={handleClick} className={className}>
            {displayText}
        </a>
    );
}