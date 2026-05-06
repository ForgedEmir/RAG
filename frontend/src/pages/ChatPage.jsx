import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useChat } from '../useChat.js';
import { useScopedLenis } from '../useLenis.js';
import { getAuthHeader } from '../auth.js';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';
import DocViewer from '../components/DocViewer.jsx';

export default function ChatPage({ user, onLogout, isAdmin }) {
  const { t } = useTranslation();
  const { sessions, activeSession, activeId, streaming, loadingHistory, newSession, selectSession, deleteSession, send, abort } = useChat();
  const [input, setInput] = useState('');
  const [activeSource, setActiveSource] = useState(null);
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
            <span>{t('chat.new_conversation')}</span>
          </button>
        </div>

        <div className="rb-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '8px 8px 12px' }}>
          <div style={{ marginBottom: 8 }}>
            {[
              { label: t('chat.documents'), icon: 'folder', path: '/docs' },
              { label: t('chat.settings'), icon: 'settings', path: '/settings' },
              { label: t('chat.monitoring'), icon: 'activity', path: '/monitoring' },
              ...(isAdmin ? [{ label: t('nav.admin'), icon: 'shield', path: '/admin' }] : []),
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

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 8px 6px' }}>
            <span className="rb-section-label" style={{ padding: 0 }}>{t('chat.conversations')}</span>
            {loadingHistory && (
              <span style={{ fontSize: 10.5, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>…</span>
            )}
          </div>
          {sessions.length === 0 && !loadingHistory && (
            <div style={{ padding: '8px 8px', fontSize: 12, color: 'var(--fg-muted)' }}>
              {t('chat.no_conversation')}
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
                  title={t('chat.delete')}
                >
                  <Icon name="x" size={11} />
                </button>
              </div>
            </div>
          ))}

          {indexedDocs.length > 0 && (
            <>
              <div style={{ height: 1, background: 'var(--border-subtle)', margin: '10px 0 8px' }} />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 8px 6px' }}>
                <span className="rb-section-label" style={{ padding: 0 }}>{t('chat.documents')}</span>
                <button
                  className="rb-btn rb-btn--ghost"
                  style={{ height: 20, padding: '0 6px', fontSize: 10.5, gap: 4 }}
                  onClick={() => navigate('/docs')}
                >
                  <Icon name="plus" size={10} />
                  {t('chat.manage')}
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
              {user?.email || t('chat.user_guest')}
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>
              {user ? t('chat.user_connected') : t('chat.user_guest_mode')}
            </div>
          </div>
          <button
            className="rb-btn rb-btn--ghost"
            style={{ width: 28, height: 28, padding: 0 }}
            onClick={onLogout}
            title={t('chat.logout')}
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
                {t('chat.assistant_heading')}
              </h1>
              {sessionDocs.length > 0 && (
                <span className="rb-pill rb-pill--ok">
                  <span className="rb-dot" />
                  {t('chat.source', { count: sessionDocs.length })}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button className="rb-btn rb-btn--ghost" style={{ gap: 6 }} onClick={() => navigate('/docs')}>
                <Icon name="upload" size={14} />
                <span>{t('chat.import')}</span>
              </button>
              <button className="rb-btn rb-btn--ghost" style={{ gap: 6 }} onClick={() => navigate('/monitoring')}>
                <Icon name="activity" size={14} />
                <span>{t('chat.monitoring')}</span>
              </button>
            </div>
          </header>

          {/* Messages */}
          <div className="rb-scroll" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '32px 0' }}>
            {!activeSession?.messages?.length ? (
              <EmptyState onSuggestion={handleSuggestion} t={t} />
            ) : (
              <div style={{ maxWidth: 760, margin: '0 auto', padding: '0 24px', display: 'flex', flexDirection: 'column', gap: 28 }}>
                {activeSession.messages.map(msg => (
                  msg.role === 'user'
                    ? <UserMsg key={msg.id} text={msg.content} />
                    : <AIMsg key={msg.id} msg={msg} activeSource={activeSource} onCiteClick={handleCiteClick} t={t} />
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
                  placeholder={t('chat.placeholder')}
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
                    title={t('chat.stop')}
                  >
                    <Icon name="stop" size={14} />
                  </button>
                ) : (
                  <button
                    className="rb-btn rb-btn--primary"
                    style={{ width: 32, height: 32, padding: 0 }}
                    onClick={handleSend}
                    disabled={!input.trim()}
                    title={t('chat.send')}
                  >
                    <Icon name="send" size={14} />
                  </button>
                )}
              </div>
              <div style={{
                marginTop: 8, fontSize: 11, color: 'var(--fg-muted)',
                display: 'flex', justifyContent: 'space-between',
              }}>
                <span>{t('chat.helper')}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{t('chat.shortcuts')}</span>
              </div>
            </div>
          </div>
        </main>

        {activeSource && (
          <DocViewer
            filename={activeSource}
            passage={activePassage}
            onClose={() => { setActiveSource(null); setActivePassage(null); }}
            resizable={true}
            defaultWidth={480}
          />
        )}
      </div>
    </div>
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

function EmptyState({ onSuggestion, t }) {
  const suggestions = [
    t('chat.suggestion_1'),
    t('chat.suggestion_2'),
    t('chat.suggestion_3'),
    t('chat.suggestion_4'),
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
        {t('chat.empty_heading')}
      </h2>
      <p style={{ fontSize: 14, color: 'var(--fg-secondary)', margin: '0 0 28px', maxWidth: 540, lineHeight: 1.55 }}>
        {t('chat.empty_desc')}
      </p>
      <div className="rb-section-label" style={{ padding: 0, marginBottom: 10 }}>{t('chat.suggestions')}</div>
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

function AIMsg({ msg, activeSource, onCiteClick, t }) {
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
          {t('chat.assistant_label')}{docCount > 0 ? ' ' + t('chat.doc_count', { count: docCount }) : ''}
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
                  title={firstPassage ? t('chat.view_passage', { src }) : t('chat.view_src', { src })}
                >
                  <Icon name="doc" size={11} style={{ color: 'inherit' }} />
                  <span className="rb-cite__doc" style={{ color: 'inherit' }}>{src}</span>
                  {passages.length > 1 && (
                    <span className="rb-cite__loc">{t('chat.excerpts', { count: passages.length })}</span>
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
