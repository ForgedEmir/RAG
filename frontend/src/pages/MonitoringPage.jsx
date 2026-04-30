import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScopedLenis } from '../useLenis.js';
import { useTranslation } from 'react-i18next';
import i18next from 'i18next';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';

const TAB_IDS = [
  { id: 'overview', key: 'monitoring.tab_overview', icon: 'activity' },
  { id: 'features', key: 'monitoring.tab_features', icon: 'cpu' },
  { id: 'logs', key: 'monitoring.tab_logs', icon: 'terminal' },
  { id: 'sources', key: 'monitoring.tab_sources', icon: 'database' },
];

async function apiFetch(path, monitoringKey, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { 'X-Monitoring-Key': monitoringKey, 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  if (res.status === 403) throw new Error('Invalid key');
  if (!res.ok) throw new Error(i18next.t('monitoring.http_error', { status: res.status }));
  return res.json();
}

// Non-throwing fetch — returns null on non-403 errors
async function apiFetchSafe(path, monitoringKey, options = {}) {
  try {
    return await apiFetch(path, monitoringKey, options);
  } catch (e) {
    if (e.message === 'Invalid key') throw e; // propagate auth errors
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
  if (m < 1) return i18next.t('monitoring.just_now');
  if (m < 60) return i18next.t('monitoring.min_ago', { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return i18next.t('monitoring.h_ago', { n: h });
  return i18next.t('monitoring.d_ago', { n: Math.floor(h / 24) });
}

export default function MonitoringPage({ user, onLogout }) {
  const { t } = useTranslation();
  const TABS = TAB_IDS.map(tab => ({ ...tab, label: t(tab.key) }));
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
      setKeyError(err.message || 'Invalid key');
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
            { label: t('monitoring.nav_conversations'), icon: 'chat', path: '/chat' },
            { label: t('monitoring.nav_documents'), icon: 'folder', path: '/docs' },
            { label: t('monitoring.nav_monitoring'), icon: 'activity', path: '/monitoring', active: true },
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
            <div className="rb-section-label" style={{ padding: 0, marginBottom: 6 }}>{t('monitoring.sections_label')}</div>
            {TABS.map(tb => (
              <div
                key={tb.id}
                className={'rb-listitem' + (tab === tb.id ? ' rb-listitem--active' : '')}
                onClick={() => setTab(tb.id)}
                style={{ height: 30, padding: '0 8px', gap: 8 }}
              >
                <Icon name={tb.icon} size={14} style={{ color: tab === tb.id ? 'var(--accent)' : 'var(--fg-secondary)' }} />
                <span className="rb-listitem__name" style={{ fontSize: 12.5 }}>{tb.label}</span>
              </div>
            ))}
          </div>
        )}
        <div style={{ flex: 1 }} />
        <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="rb-mono rb-mono--user">{userInitials}</div>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || t('chat.user_guest')}
            </div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} onClick={onLogout} title="Logout">
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
          <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{t('monitoring.page_heading')}</h1>
          {apiKey && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="rb-pill rb-pill--ok"><span className="rb-dot" />{t('monitoring.status_connected')}</span>
              <button
                className="rb-btn rb-btn--ghost"
                style={{ fontSize: 12 }}
                onClick={() => { sessionStorage.removeItem('monitoringKey'); setApiKey(''); setKeyInput(''); }}
              >
                {t('monitoring.change_key')}
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
  const { t } = useTranslation();
  return (
    <div style={{ maxWidth: 420, margin: '60px auto', textAlign: 'center' }}>
      <div style={{
        width: 48, height: 48, borderRadius: 8,
        background: 'var(--accent-soft)', color: 'var(--accent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
      }}>
        <Icon name="lock" size={22} />
      </div>
      <h2 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 8px' }}>{t('monitoring.keygate_heading')}</h2>
      <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 24px', lineHeight: 1.55 }}>
        {t('monitoring.keygate_desc')}
      </p>
      {keyError && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 6, fontSize: 12, color: 'var(--danger)', textAlign: 'left' }}>
          {keyError}
        </div>
      )}
      <form onSubmit={onSubmit} style={{ textAlign: 'left' }}>
        <label className="rb-label">{t('monitoring.keygate_label')}</label>
        <input
          className="rb-input rb-input--lg"
          type="password"
          value={keyInput}
          onChange={e => setKeyInput(e.target.value)}
          placeholder={t('monitoring.keygate_placeholder')}
          autoComplete="off"
          style={{ marginBottom: 12 }}
        />
        <button className="rb-btn rb-btn--primary rb-btn--lg rb-btn--block" type="submit">
          {t('monitoring.keygate_btn')}
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
  const { t } = useTranslation();
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
            {data.health?.status === 'ok' ? t('monitoring.health_operational') : t('monitoring.health_degraded')}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {[
            { label: t('monitoring.health_llm'), ok: h.llm_key },
            { label: t('monitoring.health_bm25'), ok: h.bm25_corpus },
            { label: t('monitoring.health_qdrant'), ok: h.qdrant },
            { label: t('monitoring.health_supabase'), ok: h.supabase },
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
        <StatCard title={t('monitoring.stat_requests')} value={s?.total_questions?.toLocaleString()} icon="message" />
        <StatCard title={t('monitoring.stat_latency')} value={s ? `${s.latency_p50}ms` : null} icon="zap" sub={s ? t('monitoring.stat_p95', { ms: s.latency_p95 }) : null} />
        <StatCard title={t('monitoring.stat_blocked')} value={s?.injections_blocked} icon="shield" />
        <StatCard title={t('monitoring.stat_errors')} value={s ? `${s.error_rate_pct}%` : null} icon="alert" sub={s ? `${s.questions_last_24h} ${t('monitoring.stat_req_24h')}` : null} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
        {/* Events */}
        <div className="rb-card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 12px' }}>
            {t('monitoring.recent_events')}
          </h3>
          <div className="rb-scroll" style={{ maxHeight: 320, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: 'var(--fg-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  <th style={{ textAlign: 'left', padding: '0 8px 8px 0', fontWeight: 600 }}>{t('monitoring.col_date')}</th>
                  <th style={{ textAlign: 'left', padding: '0 8px 8px 0', fontWeight: 600 }}>{t('monitoring.col_time')}</th>
                  <th style={{ textAlign: 'left', padding: '0 8px 8px 0', fontWeight: 600 }}>{t('monitoring.col_type')}</th>
                  <th style={{ textAlign: 'left', padding: '0 0 8px', fontWeight: 600 }}>{t('monitoring.col_detail')}</th>
                  <th style={{ textAlign: 'right', padding: '0 0 8px', fontWeight: 600 }}>{t('monitoring.col_latency')}</th>
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
                {!s && <tr><td colSpan={4} style={{ padding: '20px 0', textAlign: 'center', color: 'var(--fg-muted)' }}>{t('monitoring.loading')}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* Cache */}
        <div className="rb-card" style={{ padding: '18px 20px' }}>
          <h3 style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 16px' }}>
            {t('monitoring.cache_section')}
          </h3>
          {c ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}>
                  <span style={{ color: 'var(--fg-secondary)' }}>{t('monitoring.cache_usage')}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--ok)', fontSize: 11 }}>{c.entries} / {c.max}</span>
                </div>
                <div style={{ height: 6, background: 'var(--bg-muted)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${(c.entries / c.max) * 100}%`, height: '100%', background: 'var(--ok)', borderRadius: 3, transition: 'width 600ms ease' }} />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)' }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>{t('monitoring.cache_threshold')}</div>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>{c.threshold * 100}%</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>{t('monitoring.cache_ttl')}</div>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>{c.ttl / 3600}h</div>
                </div>
              </div>
            </div>
          ) : <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{t('monitoring.loading')}</div>}
        </div>
      </div>

      {/* Feedbacks */}
      <div className="rb-card" style={{ padding: '18px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h3 style={{ fontSize: 11, color: 'var(--fg-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
            {t('monitoring.feedbacks_section')}
          </h3>
          <span style={{ fontSize: 11, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>
            {t('monitoring.events', { count: data.feedbacks.length })}
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.feedbacks.length === 0 && (
            <div style={{ fontSize: 13, color: 'var(--fg-muted)', padding: '12px 0' }}>{t('monitoring.no_feedback')}</div>
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
                    {fb.question || t('monitoring.no_question_ctx')}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--fg-muted)', marginTop: 2, fontFamily: 'var(--font-mono)' }}>
                    {timeAgo(fb.created_at)} · {fb.trace_id || '—'}
                  </div>
                </div>
                <span className={'rb-pill ' + (good ? 'rb-pill--ok' : 'rb-pill--danger')}>
                  {good ? t('monitoring.feedback_positive') : t('monitoring.feedback_negative')}
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
  vector: 'Vector Search', bm25: 'BM25 Lexical', reranker: 'ONNX Reranker',
  contextual: 'Contextual Retrieval', reformulation: 'LLM Reformulation', pii: 'PII Masking',
  judge: 'LLM-as-Judge', feedback: 'Feedback', confidence: 'Confidence Scores',
  watchdog: 'Watchdog files', tts: 'Text-to-Speech', fallback: 'Fallback LLM',
};
const FEATURE_ICONS = {
  vector: 'database', bm25: 'doc', reranker: 'bar_chart', contextual: 'brain',
  reformulation: 'refresh', pii: 'eye_off', judge: 'scale', feedback: 'star',
  confidence: 'bar_chart', watchdog: 'eye', tts: 'volume', fallback: 'git_branch',
};

function FeaturesTab({ apiKey }) {
  const { t } = useTranslation();
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
              {t('monitoring.contextual_heading')}
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 8px' }}>{t('monitoring.context_improvement')}</h2>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: 0, lineHeight: 1.55 }}>
              {t('monitoring.contextual_desc')}
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
            <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{t('monitoring.coverage')}</div>
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
  const { t } = useTranslation();
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

  const levelButtons = [
    { value: 'ALL', labelKey: 'monitoring.log_all' },
    { value: 'INFO', labelKey: 'monitoring.log_info' },
    { value: 'WARNING', labelKey: 'monitoring.log_warning' },
    { value: 'ERROR', labelKey: 'monitoring.log_error' },
    { value: 'DEBUG', labelKey: 'monitoring.log_debug' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Icon name="search" size={13} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--fg-muted)' }} />
          <input
            className="rb-input"
            placeholder={t('monitoring.filter_logs')}
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={{ paddingLeft: 30 }}
          />
        </div>
        {levelButtons.map(({ value, labelKey }) => (
          <button
            key={value}
            className={'rb-btn ' + (levelFilter === value ? 'rb-btn--primary' : 'rb-btn--secondary')}
            style={{ minWidth: 0, padding: '0 10px', fontSize: 11 }}
            onClick={() => setLevelFilter(value)}
          >
            {t(labelKey)}
          </button>
        ))}
        <button className="rb-btn rb-btn--ghost" style={{ padding: '0 10px' }} onClick={fetchLogs} title="Refresh">
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
              {t('monitoring.no_log')}
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
  const { t } = useTranslation();
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
    if (!confirm(`Delete "${filename}" ?`)) return;
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
      if (res.ok) { fetchFiles(); setReindexMsg({ ok: true, text: `${file.name} imported and indexed.` }); }
      else { setReindexMsg({ ok: false, text: 'Import failed.' }); }
    } catch (_) {
      setReindexMsg({ ok: false, text: 'Network error.' });
    }
    setTimeout(() => setReindexMsg(null), 4000);
  };

  const handleReindex = async () => {
    if (!confirm('Start a full reindex?')) return;
    setReindexing(true);
    try {
      await apiFetch('/api/reindex', apiKey, { method: 'POST' });
      setReindexMsg({ ok: true, text: 'Reindexing started in the background.' });
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
          <h2 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 4px' }}>{t('monitoring.sources_heading')}</h2>
          <p style={{ fontSize: 12.5, color: 'var(--fg-secondary)', margin: 0 }}>
            {t('monitoring.sources_count', { count: files.length })}
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
            {reindexing ? t('monitoring.reindexing_btn') : t('monitoring.reindex_btn')}
          </button>
          <button
            className="rb-btn rb-btn--primary"
            style={{ gap: 6 }}
            onClick={() => fileInputRef.current?.click()}
          >
            <Icon name="upload" size={13} />
            {t('monitoring.import')}
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
          <span>File</span>
          <span>Status</span>
          <span />
        </div>
        {loading ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>{t('monitoring.loading')}</div>
        ) : files.length === 0 ? (
          <div style={{ padding: '48px 16px', textAlign: 'center', color: 'var(--fg-muted)', fontSize: 13 }}>{t('monitoring.no_sources')}</div>
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
              <span className="rb-dot" />{t('monitoring.status_indexed')}
            </span>
            <button
              className="rb-btn rb-btn--ghost"
              style={{ width: 28, height: 28, padding: 0, color: 'var(--fg-muted)' }}
              onClick={() => handleDelete(f)}
              title="Delete"
            >
              <Icon name="trash" size={13} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
