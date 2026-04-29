import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScopedLenis } from '../useLenis.js';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';
import { getAuthHeader } from '../auth.js';
import DocViewer from '../components/DocViewer.jsx';

export default function DocsPage({ user, onLogout }) {
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
    setUploadFiles(selected.map(f => ({ name: f.name, pct: 0, state: 'queued', file: f })));
    setUploadState('progress');

    for (let i = 0; i < selected.length; i++) {
      const f = selected[i];
      setUploadFiles(prev => prev.map((uf, idx) => idx === i ? { ...uf, state: 'indexing', pct: 10 } : uf));
      const formData = new FormData();
      formData.append('file', f);
      try {
        const authHeader = await getAuthHeader();
        const res = await fetch('/api/upload', { method: 'POST', headers: authHeader, body: formData });
        if (res.ok) {
          setUploadFiles(prev => prev.map((uf, idx) => idx === i ? { ...uf, state: 'done', pct: 100 } : uf));
        } else {
          setUploadFiles(prev => prev.map((uf, idx) => idx === i ? { ...uf, state: 'error', pct: 0 } : uf));
          setUploadState('error');
        }
      } catch (_) {
        setUploadFiles(prev => prev.map((uf, idx) => idx === i ? { ...uf, state: 'error', pct: 0 } : uf));
        setUploadState('error');
      }
    }

    const anyError = uploadFiles.some(f => f.state === 'error');
    if (!anyError) setUploadState('done');
    fetchFiles();
  };

  const handleDelete = async (filename) => {
    if (!confirm(`Delete "${filename}" de l'index ?`)) return;
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
            { label: 'Conversations', icon: 'chat', path: '/chat' },
            { label: 'Documents', icon: 'folder', path: '/docs', active: true },
            { label: 'Monitoring', icon: 'activity', path: '/monitoring' },
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
              {user?.email || 'Guest'}
            </div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} onClick={onLogout} title="Logout">
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
            <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Import des documents</h1>
            <span style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
              Accepted formats: PDF, DOCX, TXT · 50 MB max
            </span>
          </header>

          <div className="rb-scroll" style={{ flex: 1, padding: '28px 32px', overflowY: 'auto' }}>
            <div style={{ maxWidth: 800, margin: '0 auto' }}>
              {uploadState === null && (
                <DropZone
                  dragging={dragging}
                  onDragOver={e => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={e => { e.preventDefault(); setDragging(false); handleFileSelect(e.dataTransfer.files); }}
                  onBrowse={() => fileInputRef.current?.click()}
                />
              )}
              {uploadState === 'progress' && <ProgressView files={uploadFiles} />}
              {uploadState === 'done' && (
                <DoneView
                  files={uploadFiles}
                  onNewUpload={resetUpload}
                  onGoToChat={() => navigate('/chat')}
                />
              )}
              {uploadState === 'error' && (
                <ErrorView
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
                    <h2 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px' }}>Indexed documents</h2>
                    <p style={{ fontSize: 12.5, color: 'var(--fg-secondary)', margin: 0 }}>
                      {files.length} document{files.length !== 1 ? 's' : ''} in the database
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <div style={{ position: 'relative' }}>
                      <Icon name="search" size={14} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--fg-muted)' }} />
                      <input
                        className="rb-input"
                        placeholder="Search..."
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
                      <span>Import</span>
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
                    <span>Name</span>
                    <span>Status</span>
                    <span />
                    <span />
                  </div>
                  {loading ? (
                    <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>
                      Loading...
                    </div>
                  ) : filtered.length === 0 ? (
                    <div style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>
                      {search ? 'No results' : 'No indexed documents'}
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
                        <span className="rb-dot" />indexed
                      </span>
                      <button
                        className="rb-btn rb-btn--ghost"
                        style={{ width: 28, height: 28, padding: 0, color: viewerFile === f.name ? 'var(--accent)' : 'var(--fg-muted)' }}
                        onClick={() => setViewerFile(viewerFile === f.name ? null : f.name)}
                        title="Preview"
                      >
                        <Icon name="eye" size={13} />
                      </button>
                      <button
                        className="rb-btn rb-btn--ghost"
                        style={{ width: 28, height: 28, padding: 0, color: 'var(--fg-muted)' }}
                        onClick={() => handleDelete(f.name)}
                        title="Delete"
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

function DropZone({ dragging, onDragOver, onDragLeave, onDrop, onBrowse }) {
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
        Drop your documents here
      </h2>
      <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 18px' }}>
        or browse your computer to select them
      </p>
      <button className="rb-btn rb-btn--primary" onClick={onBrowse}>
        Browse files
      </button>
      <div style={{ marginTop: 24, fontSize: 11.5, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>
        PDF · DOCX · TXT · MD · CSV · JSON · XML — 50 MB per file
      </div>
    </div>
  );
}

function ProgressView({ files }) {
  return (
    <div className="rb-card" style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Indexing in progress</h2>
        <span style={{ fontSize: 12, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>
          {files.filter(f => f.state === 'done').length} / {files.length} files
        </span>
      </div>
      <p style={{ margin: '0 0 18px', fontSize: 12.5, color: 'var(--fg-secondary)' }}>
        You can close this page — indexing continues in the background.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {files.map((f, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Icon
              name={f.state === 'done' ? 'file_check' : f.state === 'error' ? 'file_warn' : 'doc'}
              size={18}
              style={{ color: f.state === 'done' ? 'var(--ok)' : f.state === 'error' ? 'var(--danger)' : 'var(--fg-secondary)' }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                <span style={{ fontSize: 11.5, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)', flex: 'none', marginLeft: 8 }}>
                  {f.state === 'queued' ? 'queued' : f.state === 'done' ? 'indexed' : f.state === 'error' ? 'error' : `${f.pct}%`}
                </span>
              </div>
              <div style={{ height: 4, background: 'var(--bg-muted)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  width: `${f.pct}%`, height: '100%',
                  background: f.state === 'done' ? 'var(--ok)' : f.state === 'error' ? 'var(--danger)' : 'var(--accent)',
                  borderRadius: 2, transition: 'width 300ms ease',
                }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DoneView({ files, onNewUpload, onGoToChat }) {
  return (
    <div className="rb-card" style={{ padding: '40px 32px', textAlign: 'center' }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%',
        background: 'var(--ok-soft)', color: 'var(--ok)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18,
      }}>
        <Icon name="check" size={22} />
      </div>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 6px' }}>Documents ready</h2>
      <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 24px' }}>
        {files.length} document{files.length > 1 ? 's' : ''} indexed and searchable{files.length > 1 ? 's' : ''} from the assistant.
      </p>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
        <button className="rb-btn rb-btn--primary" onClick={onGoToChat}>Open assistant</button>
        <button className="rb-btn rb-btn--secondary" onClick={onNewUpload}>Import d'others files</button>
      </div>
      <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--border-subtle)', textAlign: 'left' }}>
        <div className="rb-section-label" style={{ padding: 0, marginBottom: 10 }}>Summary</div>
        {files.map((f, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 0', borderBottom: i < files.length - 1 ? '1px solid var(--border-subtle)' : 'none', fontSize: 13,
          }}>
            <Icon name="file_check" size={16} style={{ color: 'var(--ok)' }} />
            <span style={{ flex: 1 }}>{f.name}</span>
            <span className="rb-pill rb-pill--ok"><span className="rb-dot" />indexed</span>
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

function ErrorView({ files, onRetry, onContinue }) {
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
            {errors.length} file{errors.length > 1 ? 's' : ''} could not be imported
          </h2>
          <p style={{ fontSize: 12.5, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.5 }}>
            {ok.length > 0 ? `${ok.length} other file${ok.length > 1 ? 's were' : ' was'} indexed successfully.` : ''}
            {' '}Check the format or file size of the rejected file.
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
              ? <span className="rb-pill rb-pill--ok"><span className="rb-dot" />indexed</span>
              : <span className="rb-pill rb-pill--danger">erreur</span>
            }
          </div>
        ))}
      </div>
      <div style={{
        padding: '14px 24px', borderTop: '1px solid var(--border-subtle)',
        background: 'var(--bg-sunken)', display: 'flex', justifyContent: 'flex-end', gap: 8,
      }}>
        <button className="rb-btn rb-btn--secondary" onClick={onRetry}>Retry</button>
        {ok.length > 0 && <button className="rb-btn rb-btn--primary" onClick={onContinue}>Continue</button>}
      </div>
    </div>
  );
}
