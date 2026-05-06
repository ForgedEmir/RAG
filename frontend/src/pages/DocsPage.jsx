import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useScopedLenis } from '../useLenis.js';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';
import { getAuthHeader } from '../auth.js';
import DocViewer from '../components/DocViewer.jsx';

export default function DocsPage({ user, onLogout, isAdmin }) {
  const { t } = useTranslation();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadState, setUploadState] = useState(null); // null | 'progress' | 'done' | 'error'
  const [uploadFiles, setUploadFiles] = useState([]);
  const [search, setSearch] = useState('');
  const [dragging, setDragging] = useState(false);
  const [viewerFile, setViewerFile] = useState(null);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const fetchFiles = async () => {
    try {
      const headers = await getAuthHeader();
      const res = await fetch('/api/sources', { headers });
      const data = await res.json();
      setFiles((data.files || []).map(f => ({ name: f, status: 'indexed' })));
    } catch (_) {}
    finally { setLoading(false); }
  };

  useEffect(() => { fetchFiles(); }, []);

  const handleFileSelect = async (fileList) => {
    const selected = Array.from(fileList);
    if (!selected.length) return;
    setUploadFiles(selected.map(f => ({ name: f.name, size: f.size, pct: 0, state: 'queued', startedAt: null, estimatedMs: null })));
    setUploadState('progress');

    let hasError = false;
    for (let i = 0; i < selected.length; i++) {
      const f = selected[i];
      const startedAt = Date.now();
      const estimatedMs = Math.min(25000, Math.max(2500, (f.size / 1024) * 10));

      setUploadFiles(prev => prev.map((uf, idx) =>
        idx === i ? { ...uf, state: 'indexing', pct: 5, startedAt, estimatedMs } : uf
      ));

      const interval = setInterval(() => {
        setUploadFiles(prev => prev.map((uf, idx) => {
          if (idx !== i || uf.state !== 'indexing') return uf;
          const elapsed = Date.now() - startedAt;
          const pct = Math.min(90, Math.round((elapsed / estimatedMs) * 90));
          return { ...uf, pct };
        }));
      }, 150);

      const formData = new FormData();
      formData.append('file', f);
      try {
        const authHeader = await getAuthHeader();
        const res = await fetch('/api/upload', { method: 'POST', headers: authHeader, body: formData });
        clearInterval(interval);
        if (res.ok) {
          setUploadFiles(prev => prev.map((uf, idx) => idx === i ? { ...uf, state: 'done', pct: 100 } : uf));
        } else {
          hasError = true;
          setUploadFiles(prev => prev.map((uf, idx) => idx === i ? { ...uf, state: 'error', pct: 0 } : uf));
        }
      } catch (_) {
        clearInterval(interval);
        hasError = true;
        setUploadFiles(prev => prev.map((uf, idx) => idx === i ? { ...uf, state: 'error', pct: 0 } : uf));
      }
    }

    if (hasError) setUploadState('error');
    else setUploadState('done');
    fetchFiles();
  };

  const handleDelete = async (filename) => {
    if (!confirm(t('docs.delete_confirm', { filename }))) return;
    try {
      const authHeader = await getAuthHeader();
      await fetch('/api/admin/delete', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ filename }),
      });
      fetchFiles();
    } catch (_) {}
  };

  const filtered = files.filter(f => f.name.toLowerCase().includes(search.toLowerCase()));
  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'G';

  const resetUpload = () => {
    setUploadState(null);
    setUploadFiles([]);
  };

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateColumns: '260px 1fr', background: 'var(--bg-app)' }}>
      {/* Sidebar */}
      <aside style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border-default)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px 14px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
          <RabeliaLogo size="md" />
        </div>
        <nav style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[
            { label: t('docs.nav_conversations'), icon: 'chat', path: '/chat' },
            { label: t('docs.nav_documents'), icon: 'folder', path: '/docs', active: true },
            { label: t('docs.nav_settings'), icon: 'settings', path: '/settings' },
            { label: t('docs.nav_monitoring'), icon: 'activity', path: '/monitoring' },
            ...(isAdmin ? [{ label: t('nav.admin'), icon: 'shield', path: '/admin' }] : []),
          ].map(item => (
            <div
              key={item.path}
              className={'rb-listitem' + (item.active ? ' rb-listitem--active' : '')}
              onClick={() => navigate(item.path)}
              style={{ height: 32, padding: '0 10px', gap: 10 }}
            >
              <Icon name={item.icon} size={15} style={{ color: item.active ? 'var(--accent)' : 'var(--fg-secondary)' }} />
              <span className="rb-listitem__name">{item.label}</span>
            </div>
          ))}
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="rb-mono rb-mono--user">{userInitials}</div>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || t('docs.user_guest')}
            </div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} onClick={onLogout} title={t('docs.logout')}>
            <Icon name="logout" size={14} />
          </button>
        </div>
      </aside>

      {/* Main + optional viewer panel */}
      <div style={{ display: 'flex', minHeight: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1, overflow: 'hidden' }}>
          <header style={{
            height: 56, padding: '0 24px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-default)',
            background: 'var(--bg-surface)',
            flexShrink: 0,
          }}>
            <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{t('docs.heading')}</h1>
            <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
              {t('docs.format_info')}
            </span>
          </header>

          <div className="rb-scroll" style={{ flex: 1, padding: '28px 32px', overflowY: 'auto' }}>
            <div style={{ maxWidth: 800, margin: '0 auto' }}>
              {uploadState === null && (
                <DropZone
                  t={t}
                  dragging={dragging}
                  onDragOver={e => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={e => { e.preventDefault(); setDragging(false); handleFileSelect(e.dataTransfer.files); }}
                  onBrowse={() => fileInputRef.current?.click()}
                />
              )}
              {uploadState === 'progress' && <ProgressView files={uploadFiles} t={t} />}
              {uploadState === 'done' && (
                <DoneView
                  t={t}
                  files={uploadFiles}
                  onNewUpload={resetUpload}
                  onGoToChat={() => navigate('/chat')}
                />
              )}
              {uploadState === 'error' && (
                <ErrorView
                  t={t}
                  files={uploadFiles}
                  onRetry={resetUpload}
                  onContinue={() => { setUploadState('done'); }}
                />
              )}

              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.txt,.md,.csv,.json,.xml"
                style={{ display: 'none' }}
                onChange={e => handleFileSelect(e.target.files)}
              />

              <div style={{ marginTop: 32 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 16 }}>
                  <div>
                    <h2 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px' }}>{t('docs.indexed_section')}</h2>
                    <p style={{ fontSize: 12.5, color: 'var(--fg-secondary)', margin: 0 }}>
                      {t('docs.doc_count', { count: files.length })}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <div style={{ position: 'relative' }}>
                      <Icon name="search" size={14} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--fg-muted)' }} />
                      <input
                        className="rb-input"
                        placeholder={t('docs.search_placeholder')}
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        style={{ paddingLeft: 32, width: 200 }}
                      />
                    </div>
                    <button
                      className="rb-btn rb-btn--primary"
                      style={{ gap: 6 }}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Icon name="plus" size={13} />
                      <span>{t('docs.import')}</span>
                    </button>
                  </div>
                </div>

                <div className="rb-card" style={{ overflow: 'hidden' }}>
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 80px 36px 36px',
                    padding: '10px 16px',
                    background: 'var(--bg-sunken)',
                    borderBottom: '1px solid var(--border-default)',
                    fontSize: 11, fontWeight: 600, letterSpacing: '0.04em',
                    textTransform: 'uppercase', color: 'var(--fg-muted)',
                  }}>
                    <span>{t('docs.col_name')}</span>
                    <span>{t('docs.col_status')}</span>
                    <span />
                    <span />
                  </div>
                  {loading ? (
                    <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>
                      {t('docs.loading')}
                    </div>
                  ) : filtered.length === 0 ? (
                    <div style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>
                      {search ? t('docs.no_results') : t('docs.no_documents')}
                    </div>
                  ) : filtered.map((f, i) => (
                    <div key={i} style={{
                      display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 80px 36px 36px',
                      padding: '10px 16px', alignItems: 'center',
                      borderBottom: i < filtered.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                      fontSize: 13,
                      background: viewerFile === f.name ? 'var(--accent-soft)' : 'transparent',
                      transition: 'background 120ms ease',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                        <FileIcon name={f.name} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                      </div>
                      <span className="rb-pill rb-pill--ok" style={{ width: 'fit-content' }}>
                        <span className="rb-dot" />{t('docs.status_indexed')}
                      </span>
                      <button
                        className="rb-btn rb-btn--ghost"
                        style={{ width: 28, height: 28, padding: 0, color: viewerFile === f.name ? 'var(--accent)' : 'var(--fg-muted)' }}
                        onClick={() => setViewerFile(viewerFile === f.name ? null : f.name)}
                        title={t('docs.preview')}
                      >
                        <Icon name="eye" size={13} />
                      </button>
                      <button
                        className="rb-btn rb-btn--ghost"
                        style={{ width: 28, height: 28, padding: 0, color: 'var(--fg-muted)' }}
                        onClick={() => handleDelete(f.name)}
                        title={t('docs.delete')}
                      >
                        <Icon name="trash" size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {viewerFile && (
          <DocViewer
            filename={viewerFile}
            passage={null}
            onClose={() => setViewerFile(null)}
            defaultWidth={520}
          />
        )}
      </div>
    </div>
  );
}

function DropZone({ t, dragging, onDragOver, onDragLeave, onDrop, onBrowse }) {
  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      style={{
        border: `1.5px dashed ${dragging ? 'var(--accent)' : 'var(--border-strong)'}`,
        borderRadius: 8,
        background: dragging ? 'var(--accent-soft)' : 'var(--bg-surface)',
        padding: '64px 32px',
        textAlign: 'center',
        transition: 'border-color 120ms ease, background 120ms ease',
      }}
    >
      <div style={{
        width: 56, height: 56, borderRadius: 10,
        background: 'var(--accent-soft)', color: 'var(--accent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        margin: '0 auto 18px',
      }}>
        <Icon name="cloud_up" size={26} />
      </div>
      <h2 style={{ fontSize: 16, fontWeight: 600, margin: '0 0 6px' }}>
        {t('docs.dropzone_heading')}
      </h2>
      <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 18px' }}>
        {t('docs.dropzone_subtitle')}
      </p>
      <button className="rb-btn rb-btn--primary" onClick={onBrowse}>
        {t('docs.browse')}
      </button>
      <div style={{ marginTop: 24, fontSize: 11.5, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>
        {t('docs.file_formats')}
      </div>
    </div>
  );
}

const STAGE_KEYS = [
  { min: 0,  max: 20, key: 'docs.stage_reading',     icon: 'doc' },
  { min: 20, max: 45, key: 'docs.stage_chunking',    icon: 'scissors' },
  { min: 45, max: 75, key: 'docs.stage_vectorizing', icon: 'cpu' },
  { min: 75, max: 100, key: 'docs.stage_indexing',   icon: 'database' },
];

function getStageLabel(t, pct, state) {
  if (state === 'queued') return t('docs.status_waiting');
  if (state === 'done') return t('docs.status_indexed_label');
  if (state === 'error') return t('docs.status_error_label');
  const s = STAGE_KEYS.find(s => pct >= s.min && pct < s.max);
  return s ? t(s.key) + '…' : t('docs.stage_indexing_default');
}

function getEta(pct, startedAt, estimatedMs) {
  if (!startedAt || pct <= 5 || pct >= 100) return null;
  const remaining = Math.max(0, estimatedMs - (Date.now() - startedAt));
  if (remaining < 1000) return '< 1 sec';
  if (remaining < 60000) return `~${Math.round(remaining / 1000)} sec`;
  return `~${Math.round(remaining / 60000)} min`;
}

function ProgressView({ files, t }) {
  const done = files.filter(f => f.state === 'done').length;
  const totalPct = files.length === 0 ? 0 : Math.round(files.reduce((acc, f) => acc + f.pct, 0) / files.length);
  const active = files.find(f => f.state === 'indexing');
  const overallEta = active ? getEta(active.pct, active.startedAt, active.estimatedMs) : null;

  return (
    <div className="rb-card" style={{ overflow: 'hidden' }}>
      <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{t('docs.indexing_heading')}</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {overallEta && (
              <span style={{ fontSize: 11.5, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>
                {t('docs.indexing_eta_remaining', { eta: overallEta })}
              </span>
            )}
            <span style={{ fontSize: 12, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
              {totalPct}%
            </span>
          </div>
        </div>
        <div style={{ height: 6, background: 'var(--bg-muted)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            width: `${totalPct}%`, height: '100%',
            background: 'linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 70%, white))',
            borderRadius: 3,
            transition: 'width 200ms ease',
          }} />
        </div>
        <div style={{ marginTop: 8, fontSize: 11.5, color: 'var(--fg-muted)' }}>
          {t('docs.indexing_helper', { done, total: files.length, plural: files.length > 1 ? 's' : '' })}
        </div>
      </div>

      <div style={{ padding: '12px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {files.map((f, i) => {
          const stageLabel = getStageLabel(t, f.pct, f.state);
          const eta = getEta(f.pct, f.startedAt, f.estimatedMs);
          const barColor = f.state === 'done' ? 'var(--ok)' : f.state === 'error' ? 'var(--danger)' : 'var(--accent)';
          return (
            <div key={i}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <Icon
                  name={f.state === 'done' ? 'file_check' : f.state === 'error' ? 'file_warn' : 'doc'}
                  size={15}
                  style={{ color: barColor, flex: 'none' }}
                />
                <span style={{ fontSize: 13, fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.name}
                </span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--fg-muted)', flex: 'none' }}>
                  {f.pct}%
                </span>
              </div>
              {/* Barre de progression du fichier */}
              <div style={{ height: 3, background: 'var(--bg-muted)', borderRadius: 2, overflow: 'hidden', marginBottom: 5 }}>
                <div style={{
                  width: `${f.pct}%`, height: '100%',
                  background: barColor, borderRadius: 2,
                  transition: 'width 200ms ease',
                }} />
              </div>
              {/* Étape courante + ETA */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  {STAGE_KEYS.map((s, si) => {
                    const active = f.state === 'indexing' && f.pct >= s.min && f.pct < s.max;
                    const past = f.state === 'done' || (f.state === 'indexing' && f.pct >= s.max);
                    return (
                      <div key={si} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <div style={{
                          width: 6, height: 6, borderRadius: '50%',
                          background: past ? 'var(--ok)' : active ? 'var(--accent)' : 'var(--bg-muted)',
                          transition: 'background 200ms ease',
                          boxShadow: active ? '0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent)' : 'none',
                        }} />
                        {si < STAGE_KEYS.length - 1 && (
                          <div style={{ width: 16, height: 1, background: past ? 'var(--ok)' : 'var(--border-subtle)' }} />
                        )}
                      </div>
                    );
                  })}
                  <span style={{ fontSize: 11, color: 'var(--fg-muted)', marginLeft: 6 }}>{stageLabel}</span>
                </div>
                {eta && (
                  <span style={{ fontSize: 11, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>{eta}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DoneView({ files, onNewUpload, onGoToChat, t }) {
  return (
    <div className="rb-card" style={{ padding: '40px 32px', textAlign: 'center' }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%',
        background: 'var(--ok-soft)', color: 'var(--ok)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18,
      }}>
        <Icon name="check" size={22} />
      </div>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 6px' }}>{t('docs.ready_heading')}</h2>
      <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 24px' }}>
        {t('docs.ready', { count: files.length })}
      </p>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
        <button className="rb-btn rb-btn--primary" onClick={onGoToChat}>{t('docs.open_assistant')}</button>
        <button className="rb-btn rb-btn--secondary" onClick={onNewUpload}>{t('docs.import_more')}</button>
      </div>
      <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--border-subtle)', textAlign: 'left' }}>
        <div className="rb-section-label" style={{ padding: 0, marginBottom: 10 }}>{t('docs.summary')}</div>
        {files.map((f, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 0', borderBottom: i < files.length - 1 ? '1px solid var(--border-subtle)' : 'none', fontSize: 13,
          }}>
            <Icon name="file_check" size={16} style={{ color: 'var(--ok)' }} />
            <span style={{ flex: 1 }}>{f.name}</span>
            <span className="rb-pill rb-pill--ok"><span className="rb-dot" />{t('docs.status_indexed')}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FileIcon({ name }) {
  const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
  const color = ext === '.pdf' ? '#e03' : ext === '.xlsx' ? '#1a8754' : ext === '.md' ? 'var(--accent)' : 'var(--fg-secondary)';
  return <Icon name="doc" size={15} style={{ color, flex: 'none' }} />;
}

function ErrorView({ files, onRetry, onContinue, t }) {
  const errors = files.filter(f => f.state === 'error');
  const ok = files.filter(f => f.state === 'done');
  return (
    <div className="rb-card" style={{ overflow: 'hidden' }}>
      <div style={{
        padding: '20px 24px', background: 'var(--danger-soft)',
        borderBottom: '1px solid var(--border-default)',
        display: 'flex', gap: 14, alignItems: 'flex-start',
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 6,
          background: '#fff', color: 'var(--danger)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none',
        }}>
          <Icon name="alert" size={18} />
        </div>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px', color: 'var(--danger)' }}>
            {t('docs.error_heading', { count: errors.length })}
          </h2>
          <p style={{ fontSize: 12.5, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.5 }}>
            {ok.length > 0 ? t('docs.error_others', { count: ok.length }) : ''}
            {' '}{t('docs.error_helper')}
          </p>
        </div>
      </div>
      <div style={{ padding: '12px 24px' }}>
        {files.map((f, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '12px 0', borderBottom: i < files.length - 1 ? '1px solid var(--border-subtle)' : 'none',
          }}>
            <Icon name={f.state === 'error' ? 'file_warn' : 'file_check'} size={20}
              style={{ color: f.state === 'error' ? 'var(--danger)' : 'var(--ok)' }} />
            <div style={{ flex: 1, fontSize: 13 }}>{f.name}</div>
            {f.state === 'done'
              ? <span className="rb-pill rb-pill--ok"><span className="rb-dot" />{t('docs.status_indexed')}</span>
              : <span className="rb-pill rb-pill--danger">{t('docs.error_pill')}</span>
            }
          </div>
        ))}
      </div>
      <div style={{
        padding: '14px 24px', borderTop: '1px solid var(--border-subtle)',
        background: 'var(--bg-sunken)', display: 'flex', justifyContent: 'flex-end', gap: 8,
      }}>
        <button className="rb-btn rb-btn--secondary" onClick={onRetry}>{t('docs.retry')}</button>
        {ok.length > 0 && <button className="rb-btn rb-btn--primary" onClick={onContinue}>{t('docs.continue')}</button>}
      </div>
    </div>
  );
}
