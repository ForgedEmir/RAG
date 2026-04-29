import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScopedLenis } from '../useLenis.js';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';

const TABS = [
  { id: 'overview', label: 'Vue d\'ensemble', icon: 'activity' },
  { id: 'features', label: 'Fonctionnalités', icon: 'cpu' },
  { id: 'logs', label: 'Journaux', icon: 'terminal' },
  { id: 'sources', label: 'Sources', icon: 'database' },
];

async function apiFetch(path, monitoringKey, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { 'X-Monitoring-Key': monitoringKey, 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  if (res.status === 403) throw new Error('Clé invalide');
  if (!res.ok) throw new Error(`Erreur HTTP: ${res.status}`);
  return res.json();
}

// Fetch qui ne throw pas — retourne null en cas d'erreur non-403
async function apiFetchSafe(path, monitoringKey, options = {}) {
  try {
    return await apiFetch(path, monitoringKey, options);
  } catch (e) {
    if (e.message === 'Clé invalide') throw e; // propagate auth errors
    return null;
  }
}

function useInterval(cb, delay) {
  const ref = useRef(cb);
  useEffect(() => { ref.current = cb; }, [cb]);
  useEffect(() => {
    if (delay == null) return;
    const id = setInterval(() => ref.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}

function fmtMs(ms) {
  if (ms == null) return '—';
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'À l\'instant';
  if (m < 60) return `Il y a ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `Il y a ${h}h`;
  return `Il y a ${Math.floor(h / 24)}j`;
}

export default function MonitoringPage({ user, onLogout }) {
  const [tab, setTab] = useState('overview');
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem('monitoringKey') || '');
  const [keyInput, setKeyInput] = useState('');
  const [keyError, setKeyError] = useState('');
  const navigate = useNavigate();
  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'G';

  const handleKeySubmit = async (e) => {
    e.preventDefault();
    setKeyError('');
    try {
      await apiFetch('/api/monitoring/stats', keyInput.trim());
      sessionStorage.setItem('monitoringKey', keyInput.trim());
      setApiKey(keyInput.trim());
    } catch (err) {
      setKeyError(err.message || 'Clé invalide');
    }
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
            { label: 'Documents', icon: 'folder', path: '/docs' },
            { label: 'Monitoring', icon: 'activity', path: '/monitoring', active: true },
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
        {apiKey && (
          <div style={{ padding: '8px 12px' }}>
            <div style={{ height: 1, background: 'var(--border-subtle)', marginBottom: 8 }} />
            <div className="rb-section-label" style={{ padding: 0, marginBottom: 6 }}>Sections</div>
            {TABS.map(t => (
              <div
                key={t.id}
                className={'rb-listitem' + (tab === t.id ? ' rb-listitem--active' : '')}
                onClick={() => setTab(t.id)}
                style={{ height: 30, padding: '0 8px', gap: 8 }}
              >
                <Icon name={t.icon} size={14} style={{ color: tab === t.id ? 'var(--accent)' : 'var(--fg-secondary)' }} />
                <span className="rb-listitem__name" style={{ fontSize: 12.5 }}>{t.label}</span>
              </div>
            ))}
          </div>
        )}
        <div style={{ flex: 1 }} />
        <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="rb-mono rb-mono--user">{userInitials}</div>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || 'Invité'}
            </div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} onClick={onLogout} title="Déconnexion">
            <Icon name="logout" size={14} />
          </button>
        </div>
      </aside>

      {/* Main */}
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <header style={{
          height: 56, padding: '0 24px', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-surface)',
        }}>
          <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Monitoring système</h1>
          {apiKey && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="rb-pill rb-pill--ok"><span className="rb-dot" />Connecté</span>
              <button
                className="rb-btn rb-btn--ghost"
                style={{ fontSize: 12 }}
                onClick={() => { sessionStorage.removeItem('monitoringKey'); setApiKey(''); setKeyInput(''); }}
              >
                Changer la clé
              </button>
            </div>
          )}
        </header>

        <div className="rb-scroll" style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
          {!apiKey ? (
            <KeyGate
              keyInput={keyInput}
              setKeyInput={setKeyInput}
              keyError={keyError}
              onSubmit={handleKeySubmit}
            />
          ) : (
            <>
              {tab === 'overview' && <OverviewTab apiKey={apiKey} />}
              {tab === 'features' && <FeaturesTab apiKey={apiKey} />}
              {tab === 'logs' && <LogsTab apiKey={apiKey} />}
              {tab === 'sources' && <SourcesTab apiKey={apiKey} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function KeyGate({ keyInput, setKeyInput, keyError, onSubmit }) {
  return (
    <div style={{ maxWidth: 420, margin: '60px auto', textAlign: 'center' }}>
      <div style={{
        width: 48, height: 48, borderRadius: 8,
        background: 'var(--accent-soft)', color: 'var(--accent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
      }}>
        <Icon name="lock" size={22} />
      </div>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 8px' }}>Accès monitoring</h2>
      <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 24px', lineHeight: 1.55 }}>
        Saisissez votre clé de monitoring pour accéder aux métriques système.
      </p>
      {keyError && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 6, fontSize: 12, color: 'var(--danger)', textAlign: 'left' }}>
          {keyError}
        </div>
      )}
      <form onSubmit={onSubmit} style={{ textAlign: 'left' }}>
        <label className="rb-label">Clé de monitoring</label>
        <input
          className="rb-input rb-input--lg"
          type="password"
          value={keyInput}
          onChange={e => setKeyInput(e.target.value)}
          placeholder="mk_••••••••"
          autoComplete="off"
          style={{ marginBottom: 12 }}
        />
        <button className="rb-btn rb-btn--primary rb-btn--lg rb-btn--block" type="submit">
          Accéder au tableau de bord
        </button>
      </form>
    </div>
  );
}

function StatCard({ title, value, icon, sub }) {
  return (
    <div className="rb-card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <span style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{title}</span>
        <Icon name={icon} size={16} style={{ color: 'var(--accent)' }} />
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--fg-primary)' }}>
        {value ?? <span style={{ opacity: 0.3 }}>—</span>}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function OverviewTab({ apiKey }) {
  const [data, setData] = useState({ health: null, stats: null, cache: null, feedbacks: [] });
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [health, stats, cache, fbResp] = await Promise.all([
        apiFetchSafe('/health', apiKey),
        apiFetchSafe('/api/monitoring/stats', apiKey),
        apiFetchSafe('/api/cache/stats', apiKey),
        apiFetchSafe('/api/monitoring/feedbacks?limit=20', apiKey),
      ]);
      setData({
        health: health || null,
        stats: stats || null,
        cache: cache || null,
        feedbacks: fbResp?.feedbacks || [],
      });
      setError(null);
    } catch (e) { setError(e.message); }
  }, [apiKey]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useInterval(fetchData, 30000);

  const h = data.health?.checks || {};
  const s = data.stats;
  const c = data.cache;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {error && (
        <div style={{ padding: '10px 14px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 6, fontSize: 13, color: 'var(--danger)' }}>
          {error}
        </div>
      )}

      {/* Health bar */}
      <div className="rb-card" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            background: data.health?.status === 'ok' ? 'var(--ok)' : 'var(--warn)',
          }} />
          <span style={{ fontSize: 15, fontWeight: 600 }}>
            {data.health?.status === 'ok' ? 'Système opérationnel' : 'Performances dégradées'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'LLM API', ok: h.llm_key },
            { label: 'Corpus BM25', ok: h.bm25_corpus },
            { label: 'Qdrant DB', ok: h.qdrant },
            { label: 'Supabase', ok: h.supabase },
          ].map((check, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-secondary)' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: check.ok ? 'var(--ok)' : 'var(--danger)' }} />
              {check.label}
            </div>
          ))}
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <StatCard title="Total requêtes" value={s?.total_questions?.toLocaleString()} icon="message" />
        <StatCard title="Latence médiane" value={s ? `${s.latency_p50}ms` : null} icon="zap" sub={s ? `P95: ${s.latency_p95}ms` : null} />
        <StatCard title="Injections bloquées" value={s?.injections_blocked} icon="shield" />
        <StatCard title="Taux d'erreur" value={s ? `${s.error_rate_pct}%` : null} icon="alert" sub={s ? `${s.questions_last_24h} req. / 24h` : null} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
        {/* Events */}
        <div className="rb-card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 12px' }}>
            Derniers événements
          </h3>
          <div className="rb-scroll" style={{ maxHeight: 320, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: 'var(--fg-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  <th style={{ textAlign: 'left', padding: '0 8px 8px 0', fontWeight: 600 }}>Date</th>
                  <th style={{ textAlign: 'left', padding: '0 8px 8px 0', fontWeight: 600 }}>Heure</th>
                  <th style={{ textAlign: 'left', padding: '0 8px 8px 0', fontWeight: 600 }}>Type</th>
                  <th style={{ textAlign: 'left', padding: '0 0 8px', fontWeight: 600 }}>Détail</th>
                  <th style={{ textAlign: 'right', padding: '0 0 8px', fontWeight: 600 }}>Latence</th>
                </tr>
              </thead>
              <tbody>
                {s?.last_events?.map((ev, i) => {
                  const isQuestion = ev.type === 'question';
                  const isError = ev.type === 'error';
                  const isInject = ev.type?.includes('injection');
                  const typeColor = isQuestion ? 'var(--ok)' : isError ? 'var(--danger)' : isInject ? 'var(--warn)' : 'var(--fg-muted)';
                  const latColor = !ev.latency_ms ? 'var(--fg-muted)' : ev.latency_ms < 1000 ? 'var(--ok)' : ev.latency_ms < 3000 ? 'var(--warn)' : 'var(--danger)';
                  const dateObj = new Date(ev.created_at);
                  return (
                    <tr key={i} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '7px 8px 7px 0', color: 'var(--fg-muted)', fontSize: 11 }}>
                        {dateObj.toLocaleDateString()}
                      </td>
                      <td style={{ padding: '7px 8px 7px 0', color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                        {dateObj.toLocaleTimeString()}
                      </td>
                      <td style={{ padding: '7px 8px 7px 0', color: typeColor, textTransform: 'capitalize' }}>
                        {ev.type?.replace('_', ' ')}
                      </td>
                      <td style={{ padding: '7px 0', color: 'var(--fg-primary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={ev.detail}>
                        {ev.detail}
                      </td>
                      <td style={{ padding: '7px 0', textAlign: 'right', color: latColor, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                        {fmtMs(ev.latency_ms)}
                      </td>
                    </tr>
                  );
                })}
                {!s && <tr><td colSpan={4} style={{ padding: '20px 0', textAlign: 'center', color: 'var(--fg-muted)' }}>Chargement…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* Cache */}
        <div className="rb-card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 16px' }}>
            Cache sémantique
          </h3>
          {c ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}>
                  <span style={{ color: 'var(--fg-secondary)' }}>Occupation</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--ok)', fontSize: 11 }}>{c.entries} / {c.max}</span>
                </div>
                <div style={{ height: 6, background: 'var(--bg-muted)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${(c.entries / c.max) * 100}%`, height: '100%', background: 'var(--ok)', borderRadius: 3, transition: 'width 600ms ease' }} />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)' }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>Seuil</div>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>{c.threshold * 100}%</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>TTL</div>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>{c.ttl / 3600}h</div>
                </div>
              </div>
            </div>
          ) : <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Chargement…</div>}
        </div>
      </div>

      {/* Feedbacks */}
      <div className="rb-card" style={{ padding: '18px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
            Derniers feedbacks
          </h3>
          <span style={{ fontSize: 11, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>
            {data.feedbacks.length} évènement(s)
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.feedbacks.length === 0 && (
            <div style={{ fontSize: 13, color: 'var(--fg-muted)', padding: '12px 0' }}>Aucun feedback récent.</div>
          )}
          {data.feedbacks.slice(0, 8).map((fb, i) => {
            const good = Number(fb.value) > 0;
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 10px', borderRadius: 6,
                background: 'var(--bg-sunken)', border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ minWidth: 0, paddingRight: 12 }}>
                  <div style={{ fontSize: 12, color: 'var(--fg-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {fb.question || 'Sans contexte question'}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--fg-muted)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                    {timeAgo(fb.created_at)} · {fb.trace_id || '—'}
                  </div>
                </div>
                <span className={'rb-pill ' + (good ? 'rb-pill--ok' : 'rb-pill--danger')}>
                  {good ? '👍 Utile' : '👎 Pas utile'}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const FEATURE_TITLES = {
  vector: 'Recherche vectorielle', bm25: 'BM25 Lexical', reranker: 'Reranker ONNX',
  contextual: 'Contextual Retrieval', reformulation: 'Reformulation LLM', pii: 'Masquage PII',
  judge: 'LLM-as-Judge', feedback: 'Feedback', confidence: 'Scores confiance',
  watchdog: 'Watchdog fichiers', tts: 'Text-to-Speech', fallback: 'Fallback LLM',
};
const FEATURE_ICONS = {
  vector: 'database', bm25: 'doc', reranker: 'bar_chart', contextual: 'brain',
  reformulation: 'refresh', pii: 'eye_off', judge: 'scale', feedback: 'star',
  confidence: 'bar_chart', watchdog: 'eye', tts: 'volume', fallback: 'git_branch',
};

function FeaturesTab({ apiKey }) {
  const [data, setData] = useState(null);
  const [ctx, setCtx] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [feat, ctxData] = await Promise.all([
        apiFetchSafe('/api/monitoring/features', apiKey),
        apiFetchSafe('/api/monitoring/contextual-retrieval', apiKey),
      ]);
      setData(feat);
      setCtx(ctxData);
    } catch (_) {}
  }, [apiKey]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useInterval(fetchData, 30000);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Contextual retrieval focus */}
      {ctx && (
        <div className="rb-card" style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 32 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
              Contextual Retrieval
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 8px' }}>Amélioration du contexte</h2>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.55 }}>
              Technique ajoutant un résumé global à chaque chunk pour préserver le sens lors de la recherche vectorielle.
            </p>
          </div>
          <div style={{ textAlign: 'center', flexShrink: 0 }}>
            <div style={{ position: 'relative', width: 80, height: 80, margin: '0 auto 8px' }}>
              <svg width="80" height="80" viewBox="0 0 80 80" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="40" cy="40" r="32" stroke="var(--bg-muted)" strokeWidth="6" fill="none" />
                <circle cx="40" cy="40" r="32" stroke="var(--ok)" strokeWidth="6" fill="none"
                  strokeDasharray="201" strokeDashoffset={201 - (ctx.coverage_pct / 100) * 201}
                  strokeLinecap="round"
                  style={{ transition: 'stroke-dashoffset 600ms ease' }}
                />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 700 }}>
                {ctx.coverage_pct}%
              </div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Couverture</div>
            <div style={{ fontSize: 11, color: 'var(--fg-secondary)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
              {ctx.with_contextual_summary} / {ctx.sample_size}
            </div>
          </div>
        </div>
      )}

      {/* Feature grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {data ? Object.entries(data).filter(([k]) => k !== 'memory').map(([key, val]) => (
          <div key={key} className="rb-card" style={{ padding: '14px 16px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 6, flexShrink: 0,
              background: val.ok ? 'var(--ok-soft)' : 'var(--danger-soft)',
              color: val.ok ? 'var(--ok)' : 'var(--danger)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon name={FEATURE_ICONS[key] || 'zap'} size={15} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{FEATURE_TITLES[key] || key}</span>
                <span className={'rb-dot'} style={{ background: val.ok ? 'var(--ok)' : 'var(--danger)' }} />
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{val.detail}</div>
            </div>
          </div>
        )) : (
          Array(9).fill(0).map((_, i) => (
            <div key={i} className="rb-card" style={{ padding: '14px 16px', height: 68, background: 'var(--bg-muted)', borderColor: 'transparent' }} />
          ))
        )}
      </div>
    </div>
  );
}

const LOG_COLORS = { INFO: 'var(--fg-secondary)', WARNING: 'var(--warn)', ERROR: 'var(--danger)', DEBUG: 'var(--fg-muted)' };

function LogsTab({ apiKey }) {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState('');
  const [levelFilter, setLevelFilter] = useState('ALL');

  const fetchLogs = useCallback(async () => {
    try {
      const { logs: l } = await apiFetch('/api/monitoring/logs', apiKey);
      setLogs(l || []);
    } catch (_) {}
  }, [apiKey]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);
  useInterval(fetchLogs, 15000);

  const filtered = logs.filter(l =>
    (levelFilter === 'ALL' || l.level === levelFilter) &&
    (!filter || l.msg?.toLowerCase().includes(filter.toLowerCase()) || l.name?.toLowerCase().includes(filter.toLowerCase()))
  );

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Icon name="search" size={13} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--fg-muted)' }} />
          <input
            className="rb-input"
            placeholder="Filtrer les logs…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={{ paddingLeft: 30 }}
          />
        </div>
        {['ALL', 'INFO', 'WARNING', 'ERROR', 'DEBUG'].map(l => (
          <button
            key={l}
            className={'rb-btn ' + (levelFilter === l ? 'rb-btn--primary' : 'rb-btn--secondary')}
            style={{ minWidth: 0, padding: '0 10px', fontSize: 11 }}
            onClick={() => setLevelFilter(l)}
          >
            {l}
          </button>
        ))}
        <button className="rb-btn rb-btn--ghost" style={{ padding: '0 10px' }} onClick={fetchLogs} title="Rafraîchir">
          <Icon name="refresh" size={14} />
        </button>
      </div>

      <div className="rb-card" style={{ overflow: 'hidden' }}>
        <div style={{
          background: 'var(--fg-primary)', color: 'var(--fg-inverse)',
          fontFamily: 'var(--font-mono)', fontSize: 11.5,
          maxHeight: 480, overflowY: 'auto',
        }} className="rb-scroll">
          {filtered.length === 0 && (
            <div style={{ padding: '24px 16px', textAlign: 'center', color: 'rgba(255,255,255,0.3)' }}>
              Aucun log correspondant
            </div>
          )}
          {filtered.map((log, i) => (
            <div key={i} style={{
              padding: '4px 12px', display: 'flex', gap: 12, alignItems: 'baseline',
              borderBottom: '1px solid rgba(255,255,255,0.04)',
            }}>
              <span style={{ color: 'rgba(255,255,255,0.3)', flexShrink: 0, fontSize: 10.5 }}>
                {new Date(log.time).toLocaleTimeString()}
              </span>
              <span style={{
                color: LOG_COLORS[log.level] || 'rgba(255,255,255,0.5)',
                flexShrink: 0, minWidth: 56, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em',
              }}>
                {log.level}
              </span>
              <span style={{ color: 'rgba(255,255,255,0.4)', flexShrink: 0, fontSize: 10 }}>{log.name}</span>
              <span style={{ color: 'rgba(255,255,255,0.85)', flex: 1 }}>{log.msg}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SourcesTab({ apiKey }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMsg, setReindexMsg] = useState(null);
  const fileInputRef = useRef(null);

  const fetchFiles = useCallback(async () => {
    try {
      const res = await apiFetch('/api/admin/sources', apiKey);
      setFiles(res.files || []);
    } catch (_) {}
    finally { setLoading(false); }
  }, [apiKey]);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  const handleDelete = async (filename) => {
    if (!confirm(`Supprimer "${filename}" ?`)) return;
    try {
      await apiFetch('/api/admin/delete', apiKey, {
        method: 'DELETE',
        body: JSON.stringify({ filename }),
      });
      fetchFiles();
    } catch (_) {}
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        headers: { 'X-Monitoring-Key': apiKey },
        body: formData,
      });
      if (res.ok) { fetchFiles(); setReindexMsg({ ok: true, text: `${file.name} importé et indexé.` }); }
      else { setReindexMsg({ ok: false, text: 'Échec de l\'import.' }); }
    } catch (_) {
      setReindexMsg({ ok: false, text: 'Erreur réseau.' });
    }
    setTimeout(() => setReindexMsg(null), 4000);
  };

  const handleReindex = async () => {
    if (!confirm('Lancer une réindexation complète ?')) return;
    setReindexing(true);
    try {
      await apiFetch('/api/reindex', apiKey, { method: 'POST' });
      setReindexMsg({ ok: true, text: 'Réindexation lancée en arrière-plan.' });
      setTimeout(() => fetchFiles(), 5000);
    } catch (e) {
      setReindexMsg({ ok: false, text: e.message });
    } finally {
      setReindexing(false);
      setTimeout(() => setReindexMsg(null), 4000);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px' }}>Sources indexées</h2>
          <p style={{ fontSize: 12.5, color: 'var(--fg-secondary)', margin: 0 }}>
            {files.length} fichier{files.length !== 1 ? 's' : ''} dans la base
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="rb-btn rb-btn--secondary"
            style={{ gap: 6 }}
            onClick={handleReindex}
            disabled={reindexing}
          >
            <Icon name="refresh" size={13} />
            {reindexing ? 'Indexation…' : 'Réindexer tout'}
          </button>
          <button
            className="rb-btn rb-btn--primary"
            style={{ gap: 6 }}
            onClick={() => fileInputRef.current?.click()}
          >
            <Icon name="upload" size={13} />
            Importer
          </button>
          <input ref={fileInputRef} type="file" style={{ display: 'none' }} onChange={handleUpload} />
        </div>
      </div>

      {reindexMsg && (
        <div style={{
          marginBottom: 12, padding: '8px 12px',
          background: reindexMsg.ok ? 'var(--ok-soft)' : 'var(--danger-soft)',
          border: `1px solid ${reindexMsg.ok ? 'var(--ok)' : 'var(--danger)'}`,
          borderRadius: 6, fontSize: 12,
          color: reindexMsg.ok ? 'var(--ok)' : 'var(--danger)',
        }}>
          {reindexMsg.text}
        </div>
      )}

      <div className="rb-card" style={{ overflow: 'hidden' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 80px 36px',
          padding: '10px 16px',
          background: 'var(--bg-sunken)', borderBottom: '1px solid var(--border-default)',
          fontSize: 11, fontWeight: 600, letterSpacing: '0.04em',
          textTransform: 'uppercase', color: 'var(--fg-muted)',
        }}>
          <span>Fichier</span>
          <span>Statut</span>
          <span />
        </div>
        {loading ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>Chargement…</div>
        ) : files.length === 0 ? (
          <div style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>Aucun fichier indexé</div>
        ) : files.map((f, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 80px 36px',
            padding: '10px 16px', alignItems: 'center',
            borderBottom: i < files.length - 1 ? '1px solid var(--border-subtle)' : 'none',
            fontSize: 13,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
              <Icon name="doc" size={15} style={{ color: 'var(--fg-secondary)', flex: 'none' }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f}</span>
            </div>
            <span className="rb-pill rb-pill--ok" style={{ width: 'fit-content' }}>
              <span className="rb-dot" />indexé
            </span>
            <button
              className="rb-btn rb-btn--ghost"
              style={{ width: 28, height: 28, padding: 0, color: 'var(--fg-muted)' }}
              onClick={() => handleDelete(f)}
              title="Supprimer"
            >
              <Icon name="trash" size={13} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
