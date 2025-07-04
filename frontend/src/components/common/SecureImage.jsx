import React, { useState, useEffect } from 'react';
import api from '../../api/axios';

const SecureImage = ({ src, alt, ...props }) => {
    const [imageSrc, setImageSrc] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        setImageSrc(null);
        setError(null);
        
        const abortController = new AbortController();

        const fetchImage = async () => {
            if (!src) return;
            try {
                let response = await api.get(src, {
                    responseType: 'blob',
                    signal: abortController.signal,
                });

                const contentType = response.headers['content-type'] || response.data.type;
                
                if (contentType && contentType.includes('svg')) {
                    
                    // SVG als Text laden
                    response = await api.get(src, {
                        responseType: 'text',
                        signal: abortController.signal,
                    });
                    
                    let svgContent = response.data;
                    
                    // Falls die SVG in HTML eingebettet ist, extrahiere sie
                    if (svgContent.includes('<div') && svgContent.includes('<svg')) {
                        
                        // Extrahiere den SVG-Teil
                        const svgMatch = svgContent.match(/<svg[^>]*>[\s\S]*?<\/svg>/i);
                        if (svgMatch) {
                            svgContent = svgMatch[0];
                        } else {
                            console.error('Could not find SVG content in HTML wrapper');
                            setError("Invalid SVG format");
                            return;
                        }
                    }
                    
                    const svgBlob = new Blob([svgContent], { type: 'image/svg+xml' });
                    const objectURL = URL.createObjectURL(svgBlob);
                    setImageSrc(objectURL);
                } else {
                    const objectURL = URL.createObjectURL(response.data);
                    setImageSrc(objectURL);
                }
            } catch (err) {
                if (err.name !== 'CanceledError') {
                    console.error("Failed to load secure image:", err);
                    setError("Could not load image.");
                }
            }
        };

        fetchImage();

        return () => {
            abortController.abort();
        };
    }, [src]);

    useEffect(() => {
        return () => {
            if (imageSrc) {
                URL.revokeObjectURL(imageSrc);
            }
        };
    }, [imageSrc]);

    if (error) {
        return <span className="image-error" {...props}>{alt || 'Image failed to load'}</span>;
    }

    if (!imageSrc) {
        return <span className="image-loading" {...props}>{alt || 'Loading image...'}</span>;
    }

    return <img src={imageSrc} alt={alt} {...props} />;
};

export default SecureImage;