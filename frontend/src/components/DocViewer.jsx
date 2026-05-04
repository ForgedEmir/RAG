import { useRef, useState, useCallback } from 'react';
import PDFViewer      from './viewers/PDFViewer.jsx';
import MarkdownViewer from './viewers/MarkdownViewer.jsx';
import DocxViewer     from './viewers/DocxViewer.jsx';
import ExcelViewer    from './viewers/ExcelViewer.jsx';
import CsvViewer      from './viewers/CsvViewer.jsx';
import TextViewer     from './viewers/TextViewer.jsx';

export function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

const PDF_EXTS   = new Set(['pdf']);
const MD_EXTS    = new Set(['md', 'markdown']);
const DOCX_EXTS  = new Set(['docx', 'doc']);
const EXCEL_EXTS = new Set(['xlsx', 'xls']);
const CSV_EXTS   = new Set(['csv']);
const TEXT_EXTS  = new Set(['txt', 'json', 'xml']);

function getExt(filename) {
  return filename.split('.').pop()?.toLowerCase() ?? '';
}

function ViewerBody({ filename, passage }) {
  const ext = getExt(filename);
  if (PDF_EXTS.has(ext))   return <PDFViewer filename={filename} passage={passage} />;
  if (MD_EXTS.has(ext))    return <MarkdownViewer filename={filename} passage={passage} />;
  if (DOCX_EXTS.has(ext))  return <DocxViewer filename={filename} passage={passage} />;
  if (EXCEL_EXTS.has(ext)) return <ExcelViewer filename={filename} passage={passage} />;
  if (CSV_EXTS.has(ext))   return <CsvViewer filename={filename} passage={passage} />;
  if (TEXT_EXTS.has(ext))  return <TextViewer filename={filename} passage={passage} />;
  return <TextViewer filename={filename} passage={passage} />;
}

const MIN_WIDTH = 320;
const MAX_WIDTH = 900;

export default function DocViewer({ filename, passage, onClose, resizable = false, defaultWidth = 480 }) {
  const [width, setWidth]       = useState(defaultWidth);
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef(null);

  const onMouseDown = useCallback((e) => {
    if (!resizable) return;
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    setDragging(true);

    const onMove = (ev) => {
      const delta = startX - ev.clientX;
      setWidth(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startW + delta)));
    };
    const onUp = () => {
      setDragging(false);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [resizable, width]);

  const basename = filename.split('/').pop();
  const fileUrl = `/api/file/${encodeFilePath(filename)}`;

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      width: resizable ? width : defaultWidth,
      minWidth: MIN_WIDTH,
      maxWidth: resizable ? MAX_WIDTH : defaultWidth,
      height: '100%',
      borderLeft: '1px solid var(--border-default)',
      background: 'var(--bg-surface)',
      position: 'relative',
      flexShrink: 0,
    }}>
      {resizable && (
        <div
          ref={dragRef}
          onMouseDown={onMouseDown}
          style={{
            position: 'absolute', left: 0, top: 0, bottom: 0, width: 4,
            cursor: 'col-resize', zIndex: 10,
          }}
        />
      )}

      {/* Transparent overlay during drag — prevents canvas/iframe from swallowing mouse events */}
      {dragging && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999, cursor: 'col-resize',
        }} />
      )}

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
        borderBottom: '1px solid var(--border-subtle)', flexShrink: 0,
        background: 'var(--bg-muted)',
      }}>
        <span style={{ flex: 1, fontSize: 12, fontWeight: 500, color: 'var(--fg-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={filename}>
          {basename}
        </span>
        <a
          href={fileUrl}
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: 11, color: 'var(--fg-muted)', textDecoration: 'none', flexShrink: 0 }}
          title="Ouvrir dans un nouvel onglet"
        >↗</a>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--fg-muted)', fontSize: 16, lineHeight: 1, padding: '0 2px', flexShrink: 0 }}
          title="Fermer"
        >×</button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <ViewerBody filename={filename} passage={passage} />
      </div>
    </div>
  );
}
