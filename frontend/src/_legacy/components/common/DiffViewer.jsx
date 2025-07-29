import React, { useEffect, useRef } from 'react';
import { createPatch } from 'diff';
import { Diff2HtmlUI } from 'diff2html/lib/ui/js/diff2html-ui-slim.js';

import 'highlight.js/styles/github.css';
import 'diff2html/bundles/css/diff2html.min.css';

const DiffViewer = ({ oldContent, newContent, oldTitle = 'Original', newTitle = 'Vergleich' }) => {
  const diffContainerRef = useRef(null);

  useEffect(() => {
    if (diffContainerRef.current) {
      diffContainerRef.current.innerHTML = ''; 

      const safeOldContent = oldContent || '';
      const safeNewContent = newContent || '';
      
      if (safeOldContent === '' && safeNewContent === '') {
        return;
      }

      const diffString = createPatch(
        'node-content.md',
        safeOldContent,
        safeNewContent,
        oldTitle,
        newTitle,
        { context: 9999 }
      );
      
      const configuration = {
        drawFileList: false,
        matching: 'lines',
        outputFormat: 'side-by-side',
        highlight: true,
        renderNothingWhenEmpty: false
      };

      const diff2htmlUi = new Diff2HtmlUI(diffContainerRef.current, diffString, configuration);
      
      diff2htmlUi.draw();
      diff2htmlUi.highlightCode();
    }
  }, [oldContent, newContent, oldTitle, newTitle]);

  return (
    <div ref={diffContainerRef}></div>
  );
};

export default DiffViewer;