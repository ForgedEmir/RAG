import { useState, useEffect } from 'react';
import { getAuthHeader } from '../../auth.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function TextViewer({ filename, passage }) {
  const [content, setContent] = useState(null);
  const [error, setError]      = useState(false);

  useEffect(() => {
    setContent(null);
    setError(false);
    getAuthHeader().then(headers =>
      fetch(`/api/file-text/${encodeFilePath(filename)}`, { headers })
        .then(r => r.ok ? r.text() : Promise.reject())
        .then(text => setContent(text))
        .catch(() => setError(true))
    );
  }, [filename]);

  if (error) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      Impossible de charger le fichier.
    </div>
  );
  if (content === null) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      Chargement…
    </div>
  );

  const preStyle = { whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'var(--font-mono)', lineHeight: 1.6, padding: 20 };

  return (
    <div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
      {/* Passage cité — toujours affiché au-dessus du document */}
      {passage && (
        <div style={{ margin: '12px 20px 0', padding: '8px 12px', background: 'rgba(250,204,21,0.15)', border: '1px solid rgba(250,204,21,0.4)', borderRadius: 6, fontSize: 12, lineHeight: 1.5 }}>
          <span style={{ fontWeight: 600, color: '#b45309', marginRight: 6 }}>Passage cité :</span>{passage}
        </div>
      )}
      <pre style={preStyle}>{content}</pre>
    </div>
  );
}
