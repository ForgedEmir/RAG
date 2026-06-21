import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { getAuthHeader } from '../../auth.js';
import { injectPassageMark } from '../../utils/highlight.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

/** Minimal RFC-4180 CSV parser — handles quoted fields with embedded commas/newlines. */
function parseCsv(text) {
  const rows = [];
  let row = [], field = '', inQuote = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuote) {
      if (ch === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') { inQuote = false; }
      else { field += ch; }
    } else {
      if (ch === '"') { inQuote = true; }
      else if (ch === ',') { row.push(field); field = ''; }
      else if (ch === '\n' || (ch === '\r' && text[i + 1] === '\n')) {
        if (ch === '\r') i++;
        row.push(field); field = '';
        if (row.some(c => c !== '')) rows.push(row);
        row = [];
      } else { field += ch; }
    }
  }
  if (field || row.length) { row.push(field); if (row.some(c => c !== '')) rows.push(row); }
  return rows;
}

const TH = { padding: '6px 12px', textAlign: 'left', fontWeight: 600, borderBottom: '2px solid var(--border-strong)', background: 'var(--bg-muted)', color: 'var(--fg-primary)', position: 'sticky', top: 0, whiteSpace: 'nowrap' };
const TD = { padding: '5px 12px', borderBottom: '1px solid var(--border-subtle)', color: 'var(--fg-primary)', whiteSpace: 'nowrap', maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis' };

export default function CsvViewer({ filename, passage }) {
  const { t } = useTranslation();
  const [rows, setRows]           = useState(null);
  const [error, setError]         = useState(false);
  const [markFound, setMarkFound] = useState(false);
  const tableRef = useRef(null);

  useEffect(() => {
    setRows(null);
    setError(false);
    setMarkFound(false);
    getAuthHeader().then(headers =>
      fetch(`/api/file-text/${encodeFilePath(filename)}`, { headers })
        .then(r => r.ok ? r.text() : Promise.reject())
        .then(text => setRows(parseCsv(text)))
        .catch(() => setError(true))
    );
  }, [filename]);

  useEffect(() => {
    if (!rows || !passage || !tableRef.current) { setMarkFound(false); return; }
    setMarkFound(false);
    let attempt = 0, tid;
    const tryMark = () => {
      const mark = injectPassageMark(tableRef.current, passage);
      if (mark) { setMarkFound(true); mark.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      else if (attempt < 3) { attempt++; tid = setTimeout(tryMark, 80 * attempt); }
    };
    tid = setTimeout(tryMark, 60);
    return () => clearTimeout(tid);
  }, [rows, passage]);

  if (error) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>{t('viewer.error_load')}</div>;
  if (!rows)  return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>{t('viewer.loading')}</div>;
  if (!rows.length) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>{t('viewer.csv_empty')}</div>;

  const [headers, ...dataRows] = rows;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
<div className="rb-scroll" style={{ flex: 1, overflow: 'auto' }}>
        <table ref={tableRef} style={{ borderCollapse: 'collapse', fontSize: 12, minWidth: '100%' }}>
          <thead>
            <tr>{headers.map((h, i) => <th key={i} style={TH}>{h || `Col ${i + 1}`}</th>)}</tr>
          </thead>
          <tbody>
            {dataRows.map((row, ri) => (
              <tr key={ri} style={{ background: ri % 2 === 0 ? 'transparent' : 'var(--bg-subtle, rgba(0,0,0,0.02))' }}>
                {headers.map((_, ci) => (
                  <td key={ci} style={{ ...TD, color: row[ci] ? 'var(--fg-primary)' : 'var(--fg-muted)' }} title={row[ci] || ''}>
                    {row[ci] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ padding: '6px 12px', fontSize: 11, color: 'var(--fg-muted)', borderTop: '1px solid var(--border-subtle)' }}>
          {t('viewer.rows', { count: dataRows.length })} · {t('viewer.cols', { count: headers.length })}
        </div>
      </div>
    </div>
  );
}
