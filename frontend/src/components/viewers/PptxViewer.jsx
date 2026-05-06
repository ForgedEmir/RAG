import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getAuthHeader } from '../../auth.js';

function encodeFilePath(filename) {
  return filename.split('/').map(encodeURIComponent).join('/');
}

export default function PptxViewer({ filename }) {
  const { t } = useTranslation();
  const canvasRef = useRef(null);
  const viewerRef = useRef(null);

  const [error, setError]               = useState(null);
  const [loading, setLoading]           = useState(true);
  const [slideCount, setSlideCount]     = useState(0);
  const [currentSlide, setCurrentSlide] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSlideCount(0);
    setCurrentSlide(0);

    (async () => {
      try {
        const mod = await import('pptxviewjs');
        const PPTXViewer = mod.PPTXViewer || (mod.default && mod.default.PPTXViewer);
        if (!PPTXViewer) throw new Error('PPTXViewer export not found');

        const headers = await getAuthHeader();
        const res = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status} fetching file`);
        const buf = await res.arrayBuffer();
        if (cancelled) return;

        const canvas = canvasRef.current;
        if (!canvas) throw new Error('Canvas element missing');

        canvas.width  = 1280;
        canvas.height = 720;

        const viewer = new PPTXViewer({
          canvas,
          debug: true,
          slideSizeMode: 'fit',
          backgroundColor: '#ffffff',
        });
        viewerRef.current = viewer;

        viewer.on('loadStart',      ()    => console.log('[PptxViewer] loadStart'));
        viewer.on('loadComplete',   (d)   => console.log('[PptxViewer] loadComplete', d));
        viewer.on('loadError',      (err) => {
          console.error('[PptxViewer] loadError', err);
          if (!cancelled) { setError(String(err?.message || err)); setLoading(false); }
        });
        viewer.on('renderStart',    (i)   => console.log('[PptxViewer] renderStart slide=', i));
        viewer.on('renderComplete', (i)   => console.log('[PptxViewer] renderComplete slide=', i));
        viewer.on('renderError',    (err) => console.error('[PptxViewer] renderError', err));
        viewer.on('slideChanged',   (i)   => {
          if (!cancelled && typeof i === 'number') setCurrentSlide(i);
        });

        console.log('[PptxViewer] loading file, bytes=', buf.byteLength);
        await viewer.loadFile(buf);
        if (cancelled) return;

        const n = viewer.getSlideCount?.() ?? 0;
        console.log('[PptxViewer] slideCount=', n);
        setSlideCount(n);
        if (n > 0) {
          await viewer.renderSlide(0, canvas);
          if (cancelled) return;
          setCurrentSlide(0);
        }
        setLoading(false);
      } catch (e) {
        console.error('[PptxViewer] error', e);
        if (!cancelled) {
          setError(String(e?.message || e));
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      try { viewerRef.current?.destroy?.(); } catch (_) {}
      viewerRef.current = null;
    };
  }, [filename]);

  const goPrev = async () => {
    const v = viewerRef.current;
    const c = canvasRef.current;
    if (!v || !c || currentSlide <= 0) return;
    try {
      await v.renderSlide(currentSlide - 1, c);
      setCurrentSlide(currentSlide - 1);
    } catch (e) { console.error('[PptxViewer] prev', e); }
  };

  const goNext = async () => {
    const v = viewerRef.current;
    const c = canvasRef.current;
    if (!v || !c || currentSlide >= slideCount - 1) return;
    try {
      await v.renderSlide(currentSlide + 1, c);
      setCurrentSlide(currentSlide + 1);
    } catch (e) { console.error('[PptxViewer] next', e); }
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#525659', overflow: 'hidden' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
        <canvas
          ref={canvasRef}
          width={1280}
          height={720}
          style={{
            maxWidth: '100%',
            height: 'auto',
            background: '#fff',
            boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
          }}
        />
        {loading && (
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', fontSize: 12, color: '#ccc' }}>
            {t('viewer.loading')}
          </div>
        )}
        {error && !loading && (
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', fontSize: 12, color: '#f87171', maxWidth: 360, textAlign: 'center' }}>
            {t('viewer.error_load')}
            <div style={{ fontSize: 10, marginTop: 6, opacity: 0.7 }}>{error}</div>
          </div>
        )}
      </div>

      {slideCount > 0 && !error && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12,
          padding: '8px 14px', borderTop: '1px solid var(--border-subtle)',
          background: 'var(--bg-muted)', flexShrink: 0,
        }}>
          <button
            onClick={goPrev}
            disabled={currentSlide <= 0}
            style={{
              background: 'none', border: '1px solid var(--border-default)', borderRadius: 4,
              padding: '4px 10px', fontSize: 12, cursor: currentSlide <= 0 ? 'default' : 'pointer',
              color: currentSlide <= 0 ? 'var(--fg-muted)' : 'var(--fg-primary)',
              opacity: currentSlide <= 0 ? 0.4 : 1,
            }}
          >‹</button>
          <span style={{ fontSize: 12, color: 'var(--fg-secondary)', minWidth: 70, textAlign: 'center' }}>
            {currentSlide + 1} / {slideCount}
          </span>
          <button
            onClick={goNext}
            disabled={currentSlide >= slideCount - 1}
            style={{
              background: 'none', border: '1px solid var(--border-default)', borderRadius: 4,
              padding: '4px 10px', fontSize: 12, cursor: currentSlide >= slideCount - 1 ? 'default' : 'pointer',
              color: currentSlide >= slideCount - 1 ? 'var(--fg-muted)' : 'var(--fg-primary)',
              opacity: currentSlide >= slideCount - 1 ? 0.4 : 1,
            }}
          >›</button>
        </div>
      )}
    </div>
  );
}
