import { useState, useEffect, useRef, useCallback } from 'react';
import { getAuthHeader } from '../../auth.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

function normCell(val) {
  return String(val ?? '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function rowMatchesPassage(row, normPassage) {
  if (!normPassage) return false;
  // The passage is a multi-row text chunk — check if the passage contains this row's content
  const rowText = row.map(normCell).filter(Boolean).join(' ');
  if (rowText.length < 4) return false;
  return normPassage.includes(rowText) || row.some(c => {
    const nc = normCell(c);
    return nc.length >= 4 && normPassage.includes(nc);
  });
}

function cellMatchesPassage(cell, normPassage) {
  if (!normPassage) return false;
  const nc = normCell(cell);
  return nc.length >= 4 && normPassage.includes(nc);
}

export default function ExcelViewer({ filename, passage }) {
  const [sheets, setSheets] = useState(null);
  const [activeSheet, setActiveSheet] = useState(0);
  const [loading, setLoading] = useState(true);
  const firstMatchRef = useRef(null);

  const normPassage = passage ? passage.replace(/\s+/g, ' ').trim().toLowerCase() : '';

  useEffect(() => {
    setLoading(true);
    setSheets(null);
    setActiveSheet(0);
    getAuthHeader().then(headers =>
      fetch(`/api/file-xlsx/${encodeFilePath(filename)}`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => setSheets(d))
        .catch(() => setSheets(null))
        .finally(() => setLoading(false))
    );
  }, [filename]);

  // Auto-scroll to first highlighted row when passage or sheet changes
  const setMatchRef = useCallback(el => {
    if (el && firstMatchRef.current !== el) {
      firstMatchRef.current = el;
      requestAnimationFrame(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    }
  }, []);

  useEffect(() => {
    firstMatchRef.current = null;
  }, [normPassage, activeSheet]);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Chargement…</div>;
  if (!sheets?.length) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Impossible de lire le fichier Excel.</div>;

  const current = sheets[activeSheet];
  let firstMatchSeen = false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {sheets.length > 1 && (
        <div style={{ display: 'flex', gap: 2, padding: '8px 16px 0', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
          {sheets.map((s, i) => (
            <button
              key={i}
              onClick={() => setActiveSheet(i)}
              style={{
                padding: '5px 12px', fontSize: 12, borderRadius: '4px 4px 0 0', border: '1px solid var(--border-default)',
                borderBottom: i === activeSheet ? '1px solid var(--bg-surface)' : undefined,
                background: i === activeSheet ? 'var(--bg-surface)' : 'var(--bg-muted)',
                color: i === activeSheet ? 'var(--fg-primary)' : 'var(--fg-secondary)',
                cursor: 'pointer', fontFamily: 'var(--font-sans)',
              }}
            >{s.sheet}</button>
          ))}
        </div>
      )}
      <div className="rb-scroll" style={{ flex: 1, overflowX: 'auto', overflowY: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', fontSize: 12, minWidth: '100%', whiteSpace: 'nowrap' }}>
          {current.headers.length > 0 && (
            <thead>
              <tr>
                {current.headers.map((h, i) => (
                  <th key={i} style={{
                    padding: '6px 12px', textAlign: 'left', fontWeight: 600,
                    borderBottom: '2px solid var(--border-strong)',
                    background: 'var(--bg-muted)', color: 'var(--fg-primary)',
                    position: 'sticky', top: 0,
                  }}>{h || '—'}</th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {current.rows.map((row, ri) => {
              const isMatch = normPassage && rowMatchesPassage(row, normPassage);
              const isFirst = isMatch && !firstMatchSeen;
              if (isFirst) firstMatchSeen = true;
              return (
                <tr
                  key={ri}
                  ref={isFirst ? setMatchRef : null}
                  style={{
                    background: isMatch
                      ? 'rgba(250,204,21,0.22)'
                      : ri % 2 === 0 ? 'transparent' : 'var(--bg-subtle, rgba(0,0,0,0.02))',
                    outline: isFirst ? '2px solid rgba(250,204,21,0.6)' : undefined,
                  }}
                >
                  {row.map((cell, ci) => {
                    const cellMatch = isMatch && normPassage && cellMatchesPassage(cell, normPassage);
                    return (
                      <td key={ci} style={{
                        padding: '5px 12px', borderBottom: '1px solid var(--border-subtle)',
                        color: cell ? 'var(--fg-primary)' : 'var(--fg-muted)',
                        background: cellMatch ? 'rgba(250,204,21,0.45)' : undefined,
                        fontWeight: cellMatch ? 600 : undefined,
                      }}>{cell || ''}</td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
