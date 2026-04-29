import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChat } from '../useChat.js';
import { useScopedLenis } from '../useLenis.js';
import { getSupabase } from '../auth.js';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';

async function getAuthHeader() {
  try {
    const sb = await getSupabase();
    if (sb) {
      const { data } = await sb.auth.getSession();
      const token = data?.session?.access_token;
      if (token) return { Authorization: `Bearer ${token}` };
    }
  } catch (_) {}
  return {};
}

export default function ChatPage({ user, onLogout }) {
  const { sessions, activeSession, activeId, streaming, loadingHistory, newSession, selectSession, deleteSession, send, abort } = useChat();
  const [input, setInput] = useState('');
  const [activeSource, setActiveSource] = useState(null); // Changed from sourcePanel
  const [indexedDocs, setIndexedDocs] = useState([]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    getAuthHeader().then(headers =>
      fetch('/api/sources', { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.files) setIndexedDocs(d.files); })
        .catch(() => {})
    );
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages]);

  // Close panel when session changes
  useEffect(() => { setActiveSource(null); }, [activeId]);

  const handleSend = () => {
    if (!input.trim() || streaming) return;
    send(input.trim(), activeId);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleTextareaChange = (e) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
  };

  const handleSuggestion = (text) => {
    setInput(text);
    textareaRef.current?.focus();
  };

  const [activePassage, setActivePassage] = useState(null);

  const handleCiteClick = (filename, passage) => {
    setActiveSource(filename);
    setActivePassage(passage || null);
  };

  useEffect(() => { setActivePassage(null); }, [activeId]);

  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'G';

  // Unique docs across all messages in the active session
  const sessionDocs = [];
  if (activeSession?.messages) {
    for (const m of activeSession.messages) {
      if (m.sources) {
        for (const s of m.sources) {
          if (!sessionDocs.includes(s)) sessionDocs.push(s);
        }
      }
    }
  }

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateColumns: '260px 1fr', background: 'var(--bg-app)', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-default)',
        display: 'flex', flexDirection: 'column',
        minHeight: 0,
      }}>
        <div style={{ padding: '16px 14px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
          <RabeliaLogo size="md" />
        </div>

        <div style={{ padding: '12px 12px 8px' }}>
          <button
            className="rb-btn rb-btn--secondary rb-btn--block"
            style={{ justifyContent: 'flex-start', gap: 8 }}
            onClick={newSession}
          >
            <Icon name="plus" size={14} />
            <span>Nouvelle conversation</span>
          </button>
        </div>

        <div className="rb-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '8px 8px 12px' }}>
          {/* Nav links */}
          <div style={{ marginBottom: 8 }}>
            {[
              { label: 'Documents', icon: 'folder', path: '/docs' },
              { label: 'Monitoring', icon: 'activity', path: '/monitoring' },
            ].map((item) => (
              <div
                key={item.path}
                className="rb-listitem"
                onClick={() => navigate(item.path)}
                style={{ height: 32, padding: '0 10px', gap: 10 }}
              >
                <Icon name={item.icon} size={15} style={{ color: 'var(--fg-secondary)' }} />
                <span className="rb-listitem__name">{item.label}</span>
              </div>
            ))}
          </div>

          <div style={{ height: 1, background: 'var(--border-subtle)', margin: '8px 0' }} />

          {/* Conversations list */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 8px 6px' }}>
            <span className="rb-section-label" style={{ padding: 0 }}>Conversations</span>
            {loadingHistory && (
              <span style={{ fontSize: 10.5, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>…</span>
            )}
          </div>
          {sessions.length === 0 && !loadingHistory && (
            <div style={{ padding: '8px 8px', fontSize: 12, color: 'var(--fg-muted)' }}>
              Aucune conversation
            </div>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className={'rb-listitem' + (s.id === activeId ? ' rb-listitem--active' : '')}
              onClick={() => selectSession(s.id)}
              style={{ height: 'auto', padding: '6px 8px', alignItems: 'flex-start', gap: 4, flexDirection: 'column' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', width: '100%', gap: 6 }}>
                <span className="rb-listitem__name" style={{ fontSize: 12.5, fontWeight: s.id === activeId ? 500 : 400 }}>
                  {s.title}
                </span>
                <button
                  className="rb-btn rb-btn--ghost"
                  style={{ width: 20, height: 20, padding: 0, marginLeft: 'auto', flex: 'none', opacity: 0.5 }}
                  onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                  title="Supprimer"
                >
                  <Icon name="x" size={11} />
                </button>
              </div>
            </div>
          ))}

          {/* All indexed documents */}
          {indexedDocs.length > 0 && (
            <>
              <div style={{ height: 1, background: 'var(--border-subtle)', margin: '10px 0 8px' }} />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 8px 6px' }}>
                <span className="rb-section-label" style={{ padding: 0 }}>Documents</span>
                <button
                  className="rb-btn rb-btn--ghost"
                  style={{ height: 20, padding: '0 6px', fontSize: 10.5, gap: 4 }}
                  onClick={() => navigate('/docs')}
                >
                  <Icon name="plus" size={10} />
                  Gérer
                </button>
              </div>
              {indexedDocs.map((doc) => {
                const isUsedInSession = sessionDocs.includes(doc);
                const isOpen = activeSource === doc;
                return (
                  <div
                    key={doc}
                    className={'rb-listitem' + (isOpen ? ' rb-listitem--active' : '')}
                    onClick={() => setActiveSource(doc)}
                    style={{ height: 'auto', padding: '5px 8px', gap: 8, cursor: 'pointer' }}
                    title={doc}
                  >
                    <Icon name="doc" size={13} style={{ color: isUsedInSession ? 'var(--accent)' : 'var(--fg-secondary)', flex: 'none' }} />
                    <span className="rb-listitem__name" style={{ fontSize: 12 }}>{doc}</span>
                    {isUsedInSession && (
                      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent)', flex: 'none' }} />
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>

        {/* User footer */}
        <div style={{
          padding: '10px 12px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div className="rb-mono rb-mono--user">{userInitials}</div>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || 'Invité'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
              {user ? 'Connecté' : 'Mode invité'}
            </div>
          </div>
          <button
            className="rb-btn rb-btn--ghost"
            style={{ width: 28, height: 28, padding: 0 }}
            onClick={onLogout}
            title="Déconnexion"
          >
            <Icon name="logout" size={14} />
          </button>
        </div>
      </aside>

      {/* Main area + optional source panel */}
      <div style={{ display: 'flex', flex: 1, minWidth: 0, overflow: 'hidden' }}>
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
          {/* Topbar */}
          <header style={{
            height: 56, padding: '0 24px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-default)',
            background: 'var(--bg-surface)',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0, letterSpacing: '-0.01em' }}>
                Assistant documentaire
              </h1>
              {sessionDocs.length > 0 && (
                <span className="rb-pill rb-pill--ok">
                  <span className="rb-dot" />
                  {sessionDocs.length} source{sessionDocs.length > 1 ? 's' : ''}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button className="rb-btn rb-btn--ghost" style={{ gap: 6 }} onClick={() => navigate('/docs')}>
                <Icon name="upload" size={14} />
                <span>Importer</span>
              </button>
              <button className="rb-btn rb-btn--ghost" style={{ gap: 6 }} onClick={() => navigate('/monitoring')}>
                <Icon name="activity" size={14} />
                <span>Monitoring</span>
              </button>
            </div>
          </header>

          {/* Messages */}
          <div className="rb-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '32px 0' }}>
            {!activeSession?.messages?.length ? (
              <EmptyState onSuggestion={handleSuggestion} />
            ) : (
              <div style={{ maxWidth: 760, margin: '0 auto', padding: '0 24px', display: 'flex', flexDirection: 'column', gap: 28 }}>
                {activeSession.messages.map(msg => (
                  msg.role === 'user'
                    ? <UserMsg key={msg.id} text={msg.content} />
                    : <AIMsg key={msg.id} msg={msg} activeSource={activeSource} onCiteClick={handleCiteClick} />
                ))}
                <div ref={messagesEndRef} style={{ height: 8 }} />
              </div>
            )}
          </div>

          {/* Composer */}
          <div style={{
            borderTop: '1px solid var(--border-default)',
            background: 'var(--bg-surface)',
            padding: '16px 24px 20px',
            flexShrink: 0,
          }}>
            <div style={{ maxWidth: 760, margin: '0 auto' }}>
              <div style={{
                display: 'flex', alignItems: 'flex-end', gap: 8,
                padding: 8,
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-strong)',
                borderRadius: 10,
                boxShadow: 'var(--shadow-1)',
              }}>
                <textarea
                  ref={textareaRef}
                  style={{
                    flex: 1, minHeight: 32, padding: '8px 4px', fontSize: 14,
                    color: 'var(--fg-primary)', background: 'transparent',
                    border: 'none', outline: 'none', resize: 'none',
                    fontFamily: 'var(--font-sans)', lineHeight: 1.5, overflowY: 'hidden',
                  }}
                  placeholder="Posez votre question sur les documents indexés…"
                  value={input}
                  onChange={handleTextareaChange}
                  onKeyDown={handleKey}
                  rows={1}
                />
                {streaming ? (
                  <button
                    className="rb-btn rb-btn--ghost"
                    style={{ width: 32, height: 32, padding: 0, color: 'var(--danger)' }}
                    onClick={abort}
                    title="Arrêter"
                  >
                    <Icon name="stop" size={14} />
                  </button>
                ) : (
                  <button
                    className="rb-btn rb-btn--primary"
                    style={{ width: 32, height: 32, padding: 0 }}
                    onClick={handleSend}
                    disabled={!input.trim()}
                    title="Envoyer"
                  >
                    <Icon name="send" size={14} />
                  </button>
                )}
              </div>
              <div style={{
                marginTop: 8, fontSize: 11, color: 'var(--fg-muted)',
                display: 'flex', justifyContent: 'space-between',
              }}>
                <span>Les réponses citent les passages des documents indexés.</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>↵ envoyer · ⇧↵ saut de ligne</span>
              </div>
            </div>
          </div>
        </main>

        {activeSource && <SourcePanel filename={activeSource} highlightPassage={activePassage} onClose={() => { setActiveSource(null); setActivePassage(null); }} />}
      </div>
    </div>
  );
}

// ── Excel viewer ─────────────────────────────────────────────────────────────

function ExcelViewer({ filename }) {
  const [sheets, setSheets] = useState(null);
  const [activeSheet, setActiveSheet] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setSheets(null);
    setActiveSheet(0);
    getAuthHeader().then(headers =>
      fetch(`/api/file-xlsx/${encodeURIComponent(filename)}`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(d => setSheets(d))
        .catch(() => setSheets(null))
        .finally(() => setLoading(false))
    );
  }, [filename]);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Chargement…</div>;
  if (!sheets?.length) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Impossible de lire le fichier Excel.</div>;

  const current = sheets[activeSheet];
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
            {current.rows.map((row, ri) => (
              <tr key={ri} style={{ background: ri % 2 === 0 ? 'transparent' : 'var(--bg-subtle, rgba(0,0,0,0.02))' }}>
                {row.map((cell, ci) => (
                  <td key={ci} style={{
                    padding: '5px 12px', borderBottom: '1px solid var(--border-subtle)',
                    color: cell ? 'var(--fg-primary)' : 'var(--fg-muted)',
                  }}>{cell || ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Source viewer panel ────────────────────────────────────────────────────────

function HighlightedText({ content, passage }) {
  const highlightRef = useRef(null);

  useEffect(() => {
    if (highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [passage, content]);

  if (!passage || !content) {
    return <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'var(--font-sans)', lineHeight: 1.6 }}>{content}</pre>;
  }

  // Normalize whitespace for matching
  const normalize = s => s.replace(/\s+/g, ' ').trim();
  const normContent = normalize(content);
  const normPassage = normalize(passage);
  const idx = normContent.indexOf(normPassage);

  if (idx === -1) {
    return (
      <>
        <div style={{ marginBottom: 12, padding: '8px 12px', background: 'rgba(250,204,21,0.15)', border: '1px solid rgba(250,204,21,0.4)', borderRadius: 6, fontSize: 12, lineHeight: 1.5, color: 'var(--fg-primary)' }}>
          <span style={{ fontWeight: 600, color: '#b45309', marginRight: 6 }}>Passage cité :</span>{passage}
        </div>
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'var(--font-sans)', lineHeight: 1.6 }}>{content}</pre>
      </>
    );
  }

  // Map back to original content positions via character alignment
  let origIdx = 0, normIdx = 0;
  const origToNorm = [];
  for (let i = 0; i < content.length; i++) {
    origToNorm.push(normIdx);
    if (content[i].trim() !== '') normIdx++;
    else if (normIdx > 0 && normContent[normIdx - 1] !== ' ' && normContent[normIdx] === ' ') normIdx++;
  }
  const startOrig = origToNorm.indexOf(idx);
  const endOrig = origToNorm.indexOf(idx + normPassage.length);

  const before = content.slice(0, startOrig !== -1 ? startOrig : 0);
  const marked = content.slice(startOrig !== -1 ? startOrig : 0, endOrig !== -1 ? endOrig : content.length);
  const after = content.slice(endOrig !== -1 ? endOrig : content.length);

  return (
    <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0, fontFamily: 'var(--font-sans)', lineHeight: 1.6 }}>
      {before}
      <mark ref={highlightRef} style={{ background: 'rgba(250,204,21,0.45)', borderRadius: 3, padding: '1px 0', color: 'inherit' }}>{marked}</mark>
      {after}
    </pre>
  );
}

function SourcePanel({ filename, highlightPassage, onClose }) {
  const ext = filename ? filename.slice(filename.lastIndexOf('.')).toLowerCase() : '';
  const isPdf = ext === '.pdf';
  const isDocx = ext === '.docx' || ext === '.doc';
  const canExtractText = new Set(['.txt', '.md', '.csv', '.json', '.xml', '.pdf', '.docx', '.doc', '.xlsx']).has(ext);

  const [content, setContent] = useState(null);
  const [token, setToken] = useState(null);
  const [loadingText, setLoadingText] = useState(false);
  const [expanded, setExpanded] = useState(false);
  // PDFs default to visual reader; toggle to text view for highlight
  const [pdfTextView, setPdfTextView] = useState(false);
  const [width, setWidth] = useState(480);
  const dragRef = useRef(null);

  useEffect(() => {
    getAuthHeader().then(h => {
      const t = h.Authorization?.split(' ')[1];
      setToken(t);
    });
  }, []);

  // Load extracted text for non-PDF text files, PDF text mode, or DOCX (always text)
  const needsTextLoad = canExtractText && (!isPdf || pdfTextView) && !(!canExtractText);
  useEffect(() => {
    if (!needsTextLoad) return;
    setLoadingText(true);
    setContent(null);
    getAuthHeader().then(headers =>
      fetch(`/api/file-text/${encodeURIComponent(filename)}`, { headers })
        .then(r => r.ok ? r.text() : null)
        .then(t => setContent(t))
        .catch(() => setContent(null))
        .finally(() => setLoadingText(false))
    );
  }, [filename, needsTextLoad]);

  // When a passage is cited on a PDF, switch to text view so highlight is visible
  useEffect(() => {
    if (highlightPassage && isPdf) setPdfTextView(true);
  }, [highlightPassage, isPdf]);

  // Reset text view when file changes
  useEffect(() => { setPdfTextView(false); }, [filename]);

  // Drag-to-resize: drag the left edge
  useEffect(() => {
    if (expanded) return;
    const handle = dragRef.current;
    if (!handle) return;
    let startX, startW;
    const onMouseDown = (e) => {
      startX = e.clientX;
      startW = width;
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
      const onMouseMove = (e) => {
        const delta = startX - e.clientX;
        setWidth(Math.max(320, Math.min(900, startW + delta)));
      };
      const onMouseUp = () => {
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      };
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    };
    handle.addEventListener('mousedown', onMouseDown);
    return () => handle.removeEventListener('mousedown', onMouseDown);
  }, [expanded, width]);

  const fileUrl = token
    ? `/api/file/${encodeURIComponent(filename)}?token=${token}`
    : `/api/file/${encodeURIComponent(filename)}`;

  const panelStyle = expanded
    ? { position: 'fixed', inset: 0, zIndex: 200, background: 'var(--bg-surface)', display: 'flex', flexDirection: 'column' }
    : { width, minWidth: 320, borderLeft: '1px solid var(--border-default)', background: 'var(--bg-surface)', display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', flexShrink: 0 };

  const body = (() => {
    // PDF visual reader (default)
    if (isPdf && !pdfTextView) {
      if (!token) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Chargement…</div>;
      return <iframe src={fileUrl} style={{ width: '100%', height: '100%', border: 'none' }} title={filename} />;
    }
    // Excel — table viewer
    if (ext === '.xlsx') return <ExcelViewer filename={filename} />;
    // Text view (txt/md/csv/json/xml + PDF text mode + DOCX)
    if (loadingText) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Chargement…</div>;
    if (canExtractText && content != null) {
      return (
        <div className="rb-scroll" style={{ padding: 20, overflowY: 'auto', height: '100%' }}>
          <HighlightedText content={content} passage={highlightPassage} />
        </div>
      );
    }
    if (!canExtractText) return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Aperçu non disponible — <a href={fileUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>télécharger</a></div>;
    return <div style={{ padding: 40, textAlign: 'center', fontSize: 12, color: 'var(--fg-muted)' }}>Impossible de charger le fichier</div>;
  })();

  return (
    <aside style={panelStyle}>
      {/* Drag handle on the left edge */}
      {!expanded && (
        <div ref={dragRef} style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: 5,
          cursor: 'ew-resize', zIndex: 10,
        }} />
      )}
      <header style={{ height: 56, padding: '0 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-default)', flexShrink: 0 }}>
        <span style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: 8 }}>{filename}</span>
        <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          {isPdf && (
            <button
              className="rb-btn rb-btn--ghost"
              style={{ width: 32, padding: 0 }}
              onClick={() => setPdfTextView(v => !v)}
              title={pdfTextView ? 'Voir le PDF (lecteur)' : 'Voir le texte extrait avec surbrillance'}
            >
              <Icon name={pdfTextView ? 'eye' : 'doc'} size={14} />
            </button>
          )}
          <button
            className="rb-btn rb-btn--ghost"
            style={{ width: 32, padding: 0 }}
            onClick={() => setExpanded(v => !v)}
            title={expanded ? 'Réduire' : 'Agrandir'}
          >
            <Icon name={expanded ? 'minimize' : 'maximize'} size={14} />
          </button>
          <a href={fileUrl} target="_blank" className="rb-btn rb-btn--ghost" style={{ width: 32, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }} rel="noreferrer" title="Ouvrir dans un nouvel onglet">
            <Icon name="external" size={14} />
          </a>
          <button className="rb-btn rb-btn--ghost" onClick={onClose} style={{ width: 32, padding: 0 }} title="Fermer">
            <Icon name="x" size={14} />
          </button>
        </div>
      </header>
      {highlightPassage && (!isPdf || pdfTextView) && (
        <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border-subtle)', background: 'rgba(250,204,21,0.08)', flexShrink: 0 }}>
          <span style={{ fontSize: 11, color: '#92400e', fontWeight: 500 }}>Passage cité surligné</span>
        </div>
      )}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {body}
      </div>
    </aside>
  );
}

// ── Markdown rendering ───────────────────────────────────────────────────────

function MarkdownText({ text }) {
  if (!text) return null;

  const renderText = (str) => {
    const parts = str.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  const lines = text.split('\n');
  const result = [];
  let listItems = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const listMatch = line.match(/^[-*]\s+(.*)/);

    if (listMatch) {
      listItems.push(listMatch[1]);
    } else {
      if (listItems.length > 0) {
        result.push(
          <ul key={`list-${i}`} style={{ margin: '8px 0 12px 24px', padding: 0, listStyleType: 'disc' }}>
            {listItems.map((item, li) => (
              <li key={li} style={{ marginBottom: '4px', paddingLeft: '4px' }}>
                {renderText(item)}
              </li>
            ))}
          </ul>
        );
        listItems = [];
      }
      result.push(
        <span key={i}>
          {renderText(line)}
          {i < lines.length - 1 ? <br /> : null}
        </span>
      );
    }
  }

  if (listItems.length > 0) {
    result.push(
      <ul key="list-last" style={{ margin: '8px 0 12px 24px', padding: 0, listStyleType: 'disc' }}>
        {listItems.map((item, li) => (
          <li key={li} style={{ marginBottom: '4px', paddingLeft: '4px' }}>
            {renderText(item)}
          </li>
        ))}
      </ul>
    );
  }

  return <>{result}</>;
}

// ── Message components ─────────────────────────────────────────────────────────

function EmptyState({ onSuggestion }) {
  const suggestions = [
    'Quelles sont les clauses de non-concurrence dans ce contrat ?',
    'Résume les points clés de ce document en 5 points.',
    'Quels documents traitent de la cession de parts sociales ?',
    'Quels sont les délais de préavis mentionnés ?',
  ];
  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '60px 24px', textAlign: 'left' }}>
      <div style={{
        width: 44, height: 44, borderRadius: 8,
        background: 'var(--accent-soft)', color: 'var(--accent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 20,
      }}>
        <Icon name="sparkle" size={20} />
      </div>
      <h2 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 8px', letterSpacing: '-0.015em' }}>
        Comment puis-je vous aider ?
      </h2>
      <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: '0 0 28px', maxWidth: 540, lineHeight: 1.55 }}>
        Posez une question en langage naturel — chaque réponse renvoie aux passages sources cités.
      </p>
      <div className="rb-section-label" style={{ padding: 0, marginBottom: 10 }}>Suggestions</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {suggestions.map((s, i) => (
          <button
            key={i}
            onClick={() => onSuggestion(s)}
            style={{
              textAlign: 'left', padding: '12px 14px',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              borderRadius: 6, cursor: 'pointer',
              fontSize: 13, color: 'var(--fg-primary)',
              fontFamily: 'var(--font-sans)', lineHeight: 1.4,
              transition: 'background 120ms ease, border-color 120ms ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.borderColor = 'var(--border-strong)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-surface)'; e.currentTarget.style.borderColor = 'var(--border-default)'; }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserMsg({ text }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{
        maxWidth: '78%', padding: '10px 14px',
        background: 'var(--accent)', color: 'var(--fg-inverse)',
        borderRadius: '10px 10px 2px 10px',
        fontSize: 14, lineHeight: 1.5, whiteSpace: 'pre-wrap',
      }}>{text}</div>
    </div>
  );
}

function AIMsg({ msg, activeSource, onCiteClick }) {
  // Build a map: source → passages cited in this specific message
  const sourcePassages = {};
  if (msg.context_chunks) {
    for (const chunk of msg.context_chunks) {
      if (!sourcePassages[chunk.source]) sourcePassages[chunk.source] = [];
      sourcePassages[chunk.source].push(chunk.passage);
    }
  }

  const docCount = msg.sources?.length || 0;
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <div style={{
        width: 28, height: 28, borderRadius: 6,
        background: 'var(--bg-muted)', color: 'var(--fg-secondary)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flex: 'none', marginTop: 2,
      }}>
        <Icon name="sparkle" size={14} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11.5, color: 'var(--fg-muted)', marginBottom: 6, letterSpacing: '0.02em' }}>
          Assistant{docCount > 0 ? ` · ${docCount} document${docCount > 1 ? 's' : ''}` : ''}
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--fg-primary)' }}>
          <MarkdownText text={msg.content} />
          {msg.streaming && <span className="streaming-cursor" />}
        </div>
        {msg.sources && msg.sources.length > 0 && (
          <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {msg.sources.map((src, i) => {
              const passages = sourcePassages[src] || [];
              const firstPassage = passages[0] || null;
              const isActive = activeSource === src;
              return (
                <button
                  key={i}
                  className="rb-cite"
                  style={{
                    cursor: 'pointer', border: 'none',
                    background: isActive ? 'var(--accent-soft)' : undefined,
                    borderColor: isActive ? 'var(--accent)' : undefined,
                    color: isActive ? 'var(--accent)' : undefined,
                  }}
                  onClick={() => onCiteClick(src, firstPassage)}
                  title={firstPassage ? `Voir le passage cité dans ${src}` : `Voir ${src}`}
                >
                  <Icon name="doc" size={11} style={{ color: 'inherit' }} />
                  <span className="rb-cite__doc" style={{ color: 'inherit' }}>{src}</span>
                  {passages.length > 1 && (
                    <span className="rb-cite__loc">{passages.length} extraits</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
