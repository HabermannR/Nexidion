// useWindowWidth.jsx
import { useState, useEffect } from 'react';

export function useWindowWidth() {
  const [width, setWidth] = useState(window.innerWidth);
  
  useEffect(() => {
    const handleResize = () => setWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    // Wichtig: Die Aufräumfunktion entfernt den Listener, um Memory Leaks zu vermeiden.
    return () => window.removeEventListener('resize', handleResize);
  }, []); // Der leere Array sorgt dafür, dass der Effekt nur einmal beim Mounten ausgeführt wird.

  return width;
}