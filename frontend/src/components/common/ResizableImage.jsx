// src/components/common/ResizableImage.jsx

import React, { useState } from 'react';
import SecureImage from './SecureImage'; // Importiert unsere bestehende Komponente
import './ResizableImage.css'; // Wir fügen auch etwas CSS für das Styling hinzu

const ResizableImage = ({ src, alt, ...props }) => {
    // State, um die aktuelle Breite in Prozent zu speichern. Startet bei 100%.
    const [width, setWidth] = useState(100);

    // Funktion zum Vergrößern der Breite (maximal 100%)
    const handleIncrease = (e) => {
        e.stopPropagation(); // Verhindert, dass Klicks auf andere Elemente durchsickern
        setWidth(prevWidth => Math.min(prevWidth + 10, 100));
    };

    // Funktion zum Verkleinern der Breite (minimal 20%)
    const handleDecrease = (e) => {
        e.stopPropagation();
        setWidth(prevWidth => Math.max(prevWidth - 10, 20));
    };

    // Die Komponente rendert einen Container, der das Bild und die Steuerelemente enthält.
    // Die Steuerelemente werden nur bei Hover über dem Container sichtbar.
    return (
        <div className="resizable-image-container" {...props}>
            {/* Das SecureImage erhält die dynamische Breite als Inline-Style */}
            <SecureImage 
                src={src} 
                alt={alt} 
                style={{ width: `${width}%`, height: 'auto' }} 
            />
            
            {/* Die Steuerelemente zur Größenanpassung */}
            <div className="resize-controls">
                <button onClick={handleDecrease} title="Bild verkleinern">-</button>
                <span className="resize-percentage">{width}%</span>
                <button onClick={handleIncrease} title="Bild vergrößern">+</button>
            </div>
        </div>
    );
};

export default ResizableImage;