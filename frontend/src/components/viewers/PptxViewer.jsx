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
  const containerRef = useRef(null);

  const [error, setError]           = useState(false);
  const [loading, setLoading]       = useState(true);
  const [slideCount, setSlideCount] = useState(0);
  const [currentSlide, setCurrentSlide] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    setSlideCount(0);
    setCurrentSlide(0);

    (async () => {
      try {
        const { PPTXViewer } = await import('pptxviewjs');

        const headers = await getAuthHeader();
        const res = await fetch(`/api/file/${encodeFilePath(filename)}`, { headers });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        if (cancelled) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const viewer = new PPTXViewer({ canvas });
        viewerRef.current = viewer;

        viewer.on('loadComplete', ({ slideCount: n }) => {
          if (cancelled) return;
          setSlideCount(n);
          setCurrentSlide(0);
          viewer.renderSlide(0, canvas);
          setLoading(false);
        });

        viewer.on('slideChanged', (i) => {
          if (!cancelled) setCurrentSlide(i);
        });

        await viewer.loadFile(new Blob([buf]));
      } catch (e) {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      viewerRef.current = null;
    };
  }, [filename]);

  const goPrev = async () => {
    const v = viewerRef.current;
    const c = canvasRef.current;
    if (!v || !c || currentSlide <= 0) return;
    await v.renderSlide(currentSlide - 1, c);
    setCurrentSlide(currentSlide - 1);
  };

  const goNext = async () => {
    const v = viewerRef.current;
    const c = canvasRef.current;
    if (!v || !c || currentSlide >= slideCount - 1) return;
    await v.renderSlide(currentSlide + 1, c);
    setCurrentSlide(currentSlide + 1);
  };

  if (error) return (
    <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>
      {t('viewer.error_load')}
    </div>
  );

  return (
    <div ref={containerRef} style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#525659', overflow: 'hidden' }}>
      <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
        <canvas
          ref={canvasRef}
          style={{
            maxWidth: '100%',
            height: 'auto',
            background: '#fff',
            boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
            display: loading ? 'none' : 'block',
          }}
        />
        {loading && (
          <div style={{ alignSelf: 'center', fontSize: 12, color: '#ccc', marginTop: 40 }}>
            {t('viewer.loading')}
          </div>
        )}
      </div>

      {slideCount > 0 && (
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
