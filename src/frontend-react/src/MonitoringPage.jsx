import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MessageSquare, Zap, Database, Shield, FileText, ArrowUpDown, 
  BookOpen, RefreshCw, EyeOff, Scale, Star, BarChart2, Eye, 
  Brain, Volume2, GitBranch, Trash2, UploadCloud, Play, 
  Pause, Check, X, Search, Copy, TerminalSquare, Server, Pencil
} from 'lucide-react';

// ============================================================================
// CONFIGURATION & STYLES GLOBAUX
// ============================================================================

// /!\ PASSEZ À FALSE POUR UTILISER VOTRE VRAI BACKEND /!\
const MOCK_MODE = false; 
const DEBUG = false;
const MOCK_MONITORING_KEY = (import.meta.env.VITE_MONITORING_MOCK_KEY || 'mock-monitoring-key').trim();

const styles = `
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.admin-root {
  --bg-color: #000000;
  --accent: #5ed29c;
  --error: #f87171;
  --warning: #fb923c;
  --info: #60a5fa;
  background: radial-gradient(ellipse at 85% 8%, rgba(94,210,156,0.05) 0%, transparent 45%),
              radial-gradient(ellipse at 10% 90%, rgba(94,210,156,0.03) 0%, transparent 40%),
              #000000;
  color: #ffffff;
  font-family: 'Inter', sans-serif;
  min-height: 100vh;
}

.font-serif-italic { font-family: 'Instrument Serif', serif; font-style: italic; }
.font-mono-custom { font-family: 'JetBrains Mono', monospace; }

.liquid-glass {
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
  position: relative;
  overflow: hidden;
}

.liquid-glass::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px;
  background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0) 100%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
`;

// ============================================================================
// HELPERS
// ============================================================================

function useInterval(callback, delay) {
  const savedCallback = useRef(callback);
  useEffect(() => { savedCallback.current = callback; }, [callback]);
  useEffect(() => {
    if (delay === null) return;
    const id = setInterval(() => savedCallback.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "À l'instant";
  if (minutes < 60) return `Il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Il y a ${hours} h`;
  return `Il y a ${Math.floor(hours / 24)} j`;
}

function fmtMs(ms) {
  if (ms == null) return "-";
  return ms < 1000 ? `${ms}ms` : `${(ms/1000).toFixed(1)}s`;
}

// ============================================================================
// MOCK API ADAPTER
// ============================================================================

const MOCK_DB = {
  health: { status: "ok", checks: { llm_key: true, bm25_corpus: true, qdrant: true, supabase: true } },
  stats: {
    total_questions: 14205, avg_latency_ms: 450, injections_blocked: 12, latency_p95: 1200, latency_p50: 380, questions_last_24h: 840, error_rate_pct: 0.5,
    last_events: Array(20).fill(0).map((_, i) => ({ type: i%5===0?'error':i%7===0?'injection_attempt':'question', detail: `Requête utilisateur #${Math.floor(Math.random()*1000)}`, latency_ms: Math.floor(Math.random() * 2000), created_at: new Date(Date.now() - i * 60000).toISOString() }))
  },
  cache: { status: "active", entries: 450, max: 1000, threshold: 0.85, ttl: 3600 },
  features: {
    vector: { ok: true, detail: "Qdrant en ligne (45.2k vecteurs)" }, bm25: { ok: true, detail: "Index chargé (12.5k chunks)" }, reranker: { ok: true, detail: "Modèle ONNX actif" }, contextual: { ok: true, detail: "Couverture 85%" }, reformulation: { ok: true, detail: "Activé" }, pii: { ok: true, detail: "Filtre regex + LLM" }, judge: { ok: true, detail: "Évaluation asynchrone" }, feedback: { ok: true, detail: "Table Supabase OK" }, confidence: { ok: true, detail: "Seuil dynamique actif" }, watchdog: { ok: true, detail: "Dossier synchronisé" }, tts: { ok: false, detail: "Clé API manquante" }, fallback: { ok: true, detail: "Mistral/Claude prêts" }
  },
  contextual: { sample_size: 150, with_contextual_summary: 128, coverage_pct: 85, status: "healthy", debug_payload_keys: ['content', 'summary'], debug_metadata_keys: ['source', 'page'] },
  reformulation_enabled: true,
  reformulation_history: [{ original: "c koi le rag", reformulated: "Qu'est-ce que la génération augmentée par la recherche (RAG) ?", timestamp: new Date().toISOString() }],
  logs: Array(50).fill(0).map((_, i) => ({ time: new Date(Date.now() - i*10000).toISOString(), level: ['INFO', 'WARNING', 'ERROR', 'DEBUG'][Math.floor(Math.random()*4)], name: 'CoreEngine', msg: `Traitement du chunk #${Math.floor(Math.random()*1000)} effectué.` })),
  pii: [{ original: "Mon email est jean@test.com", masked: "Mon email est [EMAIL]", timestamp: new Date().toISOString() }],
  memories: [{ user_id: "usr_12345", summary: "Utilisateur intéressé par le développement React et l'architecture RAG.", updated_at: new Date().toISOString() }],
  feedbacks: Array(8).fill(0).map((_, i) => ({
    created_at: new Date(Date.now() - i * 420000).toISOString(),
    source: i % 2 ? 'vote' : 'legacy',
    value: i % 3 === 0 ? -1 : 1,
    rating: i % 3 === 0 ? 1 : 5,
    trace_id: `trace_${1000 + i}`,
    question: i % 3 === 0 ? 'Réponse incomplète sur les factions' : 'Question lore classique',
  })),
  sources: { files: ["manifeste_v1.md", "architecture_rag.pdf", "logs_systeme.csv"], total: 3 }
};

async function apiFetch(path, monitoringKey, options = {}) {
  if (DEBUG) console.log(`[API Fetch] ${options.method || 'GET'} ${path}`);
  
  if (MOCK_MODE) {
    await new Promise(r => setTimeout(r, Math.random() * 400 + 200)); // Simulate network
    if (monitoringKey !== MOCK_MONITORING_KEY) throw new Error("403 Forbidden");
    
    if (path === '/health') return MOCK_DB.health;
    if (path === '/api/monitoring/stats') return MOCK_DB.stats;
    if (path === '/api/cache/stats') return MOCK_DB.cache;
    if (path === '/api/monitoring/features') return MOCK_DB.features;
    if (path === '/api/monitoring/contextual-retrieval') return MOCK_DB.contextual;
    if (path === '/api/monitoring/reformulation') return { enabled: MOCK_DB.reformulation_enabled };
    if (path === '/api/monitoring/reformulation/history') return { history: MOCK_DB.reformulation_history };
    if (path === '/api/monitoring/logs') return { logs: MOCK_DB.logs };
    if (path === '/api/monitoring/pii') return { history: MOCK_DB.pii };
    if (path === '/api/monitoring/user-memories') return { memories: MOCK_DB.memories };
    if (path.startsWith('/api/monitoring/feedbacks')) return { feedbacks: MOCK_DB.feedbacks };
    if (path === '/api/admin/sources') return MOCK_DB.sources;
    
    if (path === '/api/admin/delete' && options.method === 'DELETE') {
      const { filename } = JSON.parse(options.body);
      MOCK_DB.sources.files = MOCK_DB.sources.files.filter(f => f !== filename);
      MOCK_DB.sources.total--;
      return { message: "Deleted" };
    }
    throw new Error("404 Not Found in Mock");
  }

  // VRAI FETCH
  const res = await fetch(path, {
    ...options,
    headers: { 'X-Monitoring-Key': monitoringKey, 'Content-Type': 'application/json', ...(options.headers || {}) }
  });
  if (res.status === 403) throw new Error('Clé invalide');
  if (!res.ok) throw new Error(`Erreur HTTP: ${res.status}`);
  return res.json();
}

// ============================================================================
// COMPOSANTS UI RÉUTILISABLES
// ============================================================================

const Skeleton = ({ className }) => (
  <div className={`animate-pulse bg-white/5 rounded ${className}`}></div>
);

const Card = ({ children, className = "", delay = 0, ...props }) => (
  <motion.div 
    initial={{ opacity: 0, y: 12 }} 
    animate={{ opacity: 1, y: 0 }} 
    transition={{ duration: 0.3, delay }}
    className={`liquid-glass rounded-[16px] p-6 ${className}`}
    {...props}
  >
    {children}
  </motion.div>
);

const KpiCard = ({ title, value, icon: Icon, delay }) => (
  <Card delay={delay} className="flex flex-col gap-4">
    <div className="flex justify-between items-start">
      <span className="text-white/40 text-xs uppercase tracking-widest">{title}</span>
      <div className="p-2 rounded-full bg-[#5ed29c]/10 text-[#5ed29c]">
        <Icon size={16} />
      </div>
    </div>
    <div className="text-4xl font-serif-italic mt-2">{value ?? <Skeleton className="h-10 w-24" />}</div>
  </Card>
);

// ============================================================================
// ONGLETS (TABS)
// ============================================================================

// 1. VUE D'ENSEMBLE
const OverviewTab = ({ apiKey }) => {
  const [data, setData] = useState({ health: null, stats: null, cache: null, feedbacks: [], error: null });

  const fetchData = useCallback(async () => {
    try {
      const [health, stats, cache, feedbacksResp] = await Promise.all([
        apiFetch('/health', apiKey),
        apiFetch('/api/monitoring/stats', apiKey),
        apiFetch('/api/cache/stats', apiKey),
        apiFetch('/api/monitoring/feedbacks?limit=20', apiKey),
      ]);
      setData({ health, stats, cache, feedbacks: feedbacksResp.feedbacks || [], error: null });
    } catch (e) { setData(prev => ({ ...prev, error: e.message })); }
  }, [apiKey]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useInterval(fetchData, 30000);

  const h = data.health?.checks || {};
  const s = data.stats;
  const c = data.cache;
  const feedbacks = data.feedbacks || [];

  return (
    <div className="space-y-6">
      {/* Health Bar */}
      <Card delay={0} className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${data.health?.status === 'ok' ? 'bg-[#5ed29c] shadow-[0_0_10px_#5ed29c]' : 'bg-[#fb923c] animate-pulse'}`} />
          <span className="font-serif-italic text-2xl">{data.health?.status === 'ok' ? 'Système Opérationnel' : 'Performances Dégradées'}</span>
        </div>
        <div className="flex flex-wrap gap-6 text-xs text-white/50 uppercase tracking-widest">
          {[
            { label: 'LLM API', ok: h.llm_key },
            { label: 'Corpus BM25', ok: h.bm25_corpus },
            { label: 'Qdrant DB', ok: h.qdrant },
            { label: 'Supabase', ok: h.supabase }
          ].map((check, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={`w-1.5 h-1.5 rounded-full ${check.ok ? 'bg-[#5ed29c]' : 'bg-[#f87171]'}`} />
              {check.label}
            </div>
          ))}
        </div>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <KpiCard delay={0.05} title="Total Requêtes" value={s?.total_questions?.toLocaleString()} icon={MessageSquare} />
        <KpiCard delay={0.1} title="Latence Médiane" value={s ? `${s.latency_p50} ms` : null} icon={Zap} />
        <KpiCard delay={0.15} title="Injections Bloquées" value={s?.injections_blocked} icon={Shield} />
        <KpiCard delay={0.2} title="Taux d'erreur" value={s ? `${s.error_rate_pct}%` : null} icon={Server} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Events Table */}
        <Card delay={0.25} className="xl:col-span-2 flex flex-col h-[400px]">
          <h3 className="text-white/40 text-xs uppercase tracking-widest mb-4">Derniers Événements</h3>
          <div className="overflow-y-auto custom-scrollbar pr-2 flex-1">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-white/20 uppercase tracking-widest sticky top-0 bg-black/80 backdrop-blur pb-2">
                <tr><th className="pb-3 font-normal">Heure</th><th className="pb-3 font-normal">Type</th><th className="pb-3 font-normal">Détail</th><th className="pb-3 font-normal text-right">Latence</th></tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {s?.last_events?.map((ev, i) => {
                  let color = 'text-white/40';
                  if (ev.type === 'question') color = 'text-[#5ed29c]';
                  if (ev.type === 'error') color = 'text-[#f87171]';
                  if (ev.type.includes('injection')) color = 'text-[#fb923c]';
                  
                  let latColor = 'text-white/30';
                  if (ev.latency_ms) {
                    if (ev.latency_ms < 1000) latColor = 'text-[#5ed29c]';
                    else if (ev.latency_ms < 3000) latColor = 'text-[#fb923c]';
                    else latColor = 'text-[#f87171]';
                  }

                  return (
                    <motion.tr initial={{opacity:0}} animate={{opacity:1}} transition={{delay: i*0.02}} key={i} className="hover:bg-white/5 transition-colors">
                      <td className="py-3 text-white/30 text-xs">{new Date(ev.created_at).toLocaleTimeString()}</td>
                      <td className={`py-3 ${color} capitalize text-xs`}>{ev.type.replace('_', ' ')}</td>
                      <td className="py-3 text-white/70 truncate max-w-[200px]">{ev.detail}</td>
                      <td className={`py-3 text-right font-mono-custom text-xs ${latColor}`}>{fmtMs(ev.latency_ms)}</td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
            {!s && <div className="space-y-3 mt-4">{[1,2,3,4].map(i => <Skeleton key={i} className="h-8 w-full" />)}</div>}
          </div>
        </Card>

        {/* Cache Status */}
        <Card delay={0.3} className="flex flex-col">
          <h3 className="text-white/40 text-xs uppercase tracking-widest mb-6">Cache Sémantique</h3>
          {c ? (
            <div className="space-y-8 flex-1 flex flex-col justify-center">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-white/70">Occupation</span>
                  <span className="font-mono-custom text-[#5ed29c]">{c.entries} / {c.max}</span>
                </div>
                <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }} 
                    animate={{ width: `${(c.entries / c.max) * 100}%` }} 
                    className="h-full bg-[#5ed29c]" 
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 border-t border-white/5 pt-6">
                <div>
                  <div className="text-white/30 text-[10px] uppercase tracking-widest mb-1">Seuil Similitude</div>
                  <div className="text-xl font-serif-italic">{c.threshold * 100}%</div>
                </div>
                <div>
                  <div className="text-white/30 text-[10px] uppercase tracking-widest mb-1">TTL (Durée de vie)</div>
                  <div className="text-xl font-serif-italic">{c.ttl / 3600}h</div>
                </div>
              </div>
            </div>
          ) : <Skeleton className="flex-1 w-full" />}
        </Card>
      </div>

      <Card delay={0.35} className="flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white/40 text-xs uppercase tracking-widest">Derniers Feedbacks Utilisateur</h3>
          <span className="text-[10px] text-white/30">{feedbacks.length} évènement(s)</span>
        </div>
        <div className="space-y-2 max-h-[220px] overflow-y-auto custom-scrollbar pr-1">
          {feedbacks.length === 0 && (
            <div className="text-sm text-white/40">Aucun feedback récent.</div>
          )}
          {feedbacks.map((fb, i) => {
            const good = Number(fb.value) > 0;
            return (
              <div key={`${fb.trace_id || 'fb'}-${i}`} className="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="min-w-0 pr-4">
                  <div className="text-[11px] text-white/70 truncate">{fb.question || 'Sans contexte question'}</div>
                  <div className="text-[10px] text-white/30 mt-1">{new Date(fb.created_at).toLocaleTimeString()} · {fb.source || 'vote'} · {fb.trace_id || '-'}</div>
                </div>
                <div className={`text-[11px] px-2 py-1 rounded-full border ${good ? 'text-[#5ed29c] border-[#5ed29c]/30 bg-[#5ed29c]/10' : 'text-[#f87171] border-[#f87171]/30 bg-[#f87171]/10'}`}>
                  {good ? 'Utile' : 'Pas utile'}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
};

// 3. FEATURES
const FeatureGridTab = ({ apiKey }) => {
  const [data, setData] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [feat, ctx] = await Promise.all([
        apiFetch('/api/monitoring/features', apiKey),
        apiFetch('/api/monitoring/contextual-retrieval', apiKey)
      ]);
      setData({ feat, ctx });
    } catch(e) {}
  }, [apiKey]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useInterval(fetchData, 30000);

  const icons = {
    vector: Database, bm25: FileText, reranker: ArrowUpDown, contextual: BookOpen,
    reformulation: RefreshCw, pii: EyeOff, judge: Scale, feedback: Star,
    confidence: BarChart2, watchdog: Eye, tts: Volume2, fallback: GitBranch
  };

  const titles = {
    vector: "Recherche Vectorielle", bm25: "BM25 Lexical", reranker: "Reranker ONNX",
    contextual: "Contextual Retrieval", reformulation: "Reformulation LLM", pii: "Masquage PII",
    judge: "LLM-as-Judge", feedback: "Système Feedback", confidence: "Scores Confiance",
    watchdog: "Watchdog Fichiers", tts: "Text-to-Speech", fallback: "Fallback Multi-LLM"
  };

  return (
    <div className="space-y-6">
      {/* Contextual Focus */}
      <Card delay={0} className="flex flex-col md:flex-row items-center justify-between gap-8 py-8">
        <div>
          <div className="text-[#5ed29c] text-xs font-bold uppercase tracking-widest mb-2 flex items-center gap-2">
            <BookOpen size={14}/> Contextual Retrieval
          </div>
          <h2 className="text-3xl font-serif-italic mb-2">Amélioration du Contexte</h2>
          <p className="text-sm text-white/50 max-w-md">Technique avancée ajoutant un résumé global à chaque chunk pour préserver le sens lors de la recherche vectorielle.</p>
        </div>
        
        {data?.ctx ? (
          <div className="flex items-center gap-8">
            <div className="relative w-24 h-24 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90">
                <circle cx="48" cy="48" r="40" stroke="rgba(255,255,255,0.1)" strokeWidth="6" fill="none" />
                <circle cx="48" cy="48" r="40" stroke="#5ed29c" strokeWidth="6" fill="none" strokeDasharray="251.2" strokeDashoffset={251.2 - (data.ctx.coverage_pct/100)*251.2} strokeLinecap="round" className="transition-all duration-1000" />
              </svg>
              <div className="absolute font-serif-italic text-2xl">{data.ctx.coverage_pct}%</div>
            </div>
            <div className="space-y-2 text-xs text-white/40 uppercase tracking-widest">
              <div>Échantillon: <span className="text-white font-mono-custom">{data.ctx.sample_size}</span></div>
              <div>Avec résumé: <span className="text-[#5ed29c] font-mono-custom">{data.ctx.with_contextual_summary}</span></div>
            </div>
          </div>
        ) : <Skeleton className="w-48 h-24" />}
      </Card>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {data?.feat ? Object.entries(data.feat).filter(([key]) => key !== 'memory').map(([key, val], i) => {
          const Icon = icons[key] || Database;
          return (
            <motion.div key={key} initial={{opacity:0, scale:0.95}} animate={{opacity:1, scale:1}} transition={{delay: i*0.05}} className="liquid-glass p-5 rounded-2xl flex flex-col gap-3 border border-white/5 hover:bg-white/5 transition-colors">
              <div className="flex justify-between items-start">
                <Icon size={20} className={val.ok ? 'text-white/70' : 'text-[#f87171]'} />
                <div className={`w-2 h-2 rounded-full ${val.ok ? 'bg-[#5ed29c]' : 'bg-[#f87171] animate-pulse'}`} />
              </div>
              <div>
                <h4 className="text-sm font-medium">{titles[key] || key}</h4>
                <p className="text-[10px] text-white/40 mt-1 uppercase tracking-widest">{val.detail}</p>
              </div>
            </motion.div>
          );
        }) : Array(12).fill(0).map((_,i) => <Skeleton key={i} className="h-28 w-full" />)}
      </div>
    </div>
  );
};

// ── Pipeline flow visualization (inline dans SourcesTab) ─────────────────────
const INGESTION_STEPS = [
  { id: 'reception', label: 'Réception',  Icon: UploadCloud, desc: 'Validation extension, taille & sécurité' },
  { id: 'parsing',   label: 'Parsing',    Icon: FileText,    desc: 'Extraction texte, nettoyage Unicode'     },
  { id: 'chunking',  label: 'Chunking',   Icon: GitBranch,   desc: 'Découpage contextuel + late chunking'    },
  { id: 'embedding', label: 'Embedding',  Icon: Brain,       desc: 'Vecteurs ONNX 384 dim via FastEmbed'     },
  { id: 'qdrant',    label: 'Qdrant',     Icon: Database,    desc: 'Upsert vectoriel + index HNSW cosine'    },
  { id: 'bm25',      label: 'BM25',       Icon: Search,      desc: 'Rebuild corpus lexical + cache invalide' },
];

const _STEP_STYLES = {
  idle:          { ring: 'border-white/[0.06]',    bg: 'bg-transparent',      ico: 'text-white/[0.18]', lbl: 'text-white/[0.18]' },
  pending:       { ring: 'border-white/10',         bg: 'bg-white/[0.03]',     ico: 'text-white/25',     lbl: 'text-white/25'     },
  'in-progress': { ring: 'border-[#60a5fa]/60',    bg: 'bg-[#60a5fa]/10',     ico: 'text-[#60a5fa]',    lbl: 'text-[#60a5fa]'    },
  completed:     { ring: 'border-[#5ed29c]/45',    bg: 'bg-[#5ed29c]/[0.07]', ico: 'text-[#5ed29c]',    lbl: 'text-[#5ed29c]'    },
  failed:        { ring: 'border-[#f87171]/45',    bg: 'bg-[#f87171]/[0.07]', ico: 'text-[#f87171]',    lbl: 'text-[#f87171]'    },
};

const _StepNode = ({ step, status, isLast }) => {
  const s = _STEP_STYLES[status] || _STEP_STYLES.idle;
  const { Icon } = step;
  const icon = status === 'completed'
    ? <Check size={13} />
    : status === 'failed'
      ? <X size={13} />
      : <Icon size={14} />;

  return (
    <div className="flex items-start flex-1 min-w-0">
      <div className="flex flex-col items-center flex-1 min-w-0 px-1">
        <motion.div
          className={`w-9 h-9 rounded-full border flex items-center justify-center flex-shrink-0 ${s.ring} ${s.bg} ${s.ico} transition-colors duration-500`}
          animate={status === 'in-progress' ? {
            boxShadow: ['0 0 0 0 rgba(96,165,250,0)', '0 0 0 7px rgba(96,165,250,0.14)', '0 0 0 0 rgba(96,165,250,0)']
          } : { boxShadow: '0 0 0 0 rgba(0,0,0,0)' }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        >
          {icon}
        </motion.div>
        <motion.span
          className={`text-[9px] uppercase tracking-widest mt-2 font-medium text-center ${s.lbl} transition-colors duration-500`}
        >
          {step.label}
        </motion.span>
        <span className="text-[8px] text-white/12 text-center leading-snug mt-0.5 px-0.5 hidden xl:block">
          {step.desc}
        </span>
      </div>
      {!isLast && (
        <div className="flex-shrink-0 flex items-center" style={{ width: '20px', paddingTop: '18px' }}>
          <div className="h-px w-full transition-colors duration-700"
            style={{ background: status === 'completed' ? 'rgba(94,210,156,0.25)' : 'rgba(255,255,255,0.05)' }} />
        </div>
      )}
    </div>
  );
};

const IngestionFlowVis = ({ currentStep, hasError }) => {
  const getStatus = (i) => {
    if (currentStep === -1) return 'idle';
    if (hasError && i === currentStep) return 'failed';
    if (currentStep === 6 || i < currentStep) return 'completed';
    if (i === currentStep) return 'in-progress';
    return 'pending';
  };

  return (
    <div className="liquid-glass rounded-2xl px-5 py-4">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[9px] uppercase tracking-widest text-white/20 font-medium">
          Ce qui se passe lors de l'indexation
        </span>
        <AnimatePresence mode="wait">
          {currentStep === 6 && (
            <motion.span key="done" initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
              className="text-[9px] text-[#5ed29c] flex items-center gap-1">
              <Check size={9} /> Indexation terminée
            </motion.span>
          )}
          {currentStep >= 0 && currentStep < 6 && !hasError && (
            <motion.span key="running" initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
              className="text-[9px] text-[#60a5fa] flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#60a5fa] animate-pulse inline-block" />
              Traitement en cours
            </motion.span>
          )}
          {hasError && (
            <motion.span key="error" initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
              className="text-[9px] text-[#f87171] flex items-center gap-1">
              <X size={9} /> Erreur d'indexation
            </motion.span>
          )}
        </AnimatePresence>
      </div>
      <div className="flex items-start">
        {INGESTION_STEPS.map((step, i) => (
          <_StepNode key={step.id} step={step} status={getStatus(i)} isLast={i === INGESTION_STEPS.length - 1} />
        ))}
      </div>
    </div>
  );
};

// 4. SOURCES
const SourcesTab = ({ apiKey }) => {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState(null); // { ok: bool, text: string }
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef(null);
  const replaceInputRef = useRef(null);
  const [replaceTarget, setReplaceTarget] = useState('');
  const replaceTargetRef = useRef('');
  const ignoreNextUploadZoneClickRef = useRef(false);

  // ── Pipeline flow animation ───────────────────────────────────────────────
  const [pipelineStep, setPipelineStep] = useState(-1); // -1=idle, 0-5=active, 6=done
  const [pipelineError, setPipelineError] = useState(false);
  const pipelineTimersRef = useRef([]);

  const startPipelineAnim = () => {
    pipelineTimersRef.current.forEach(t => clearTimeout(t));
    pipelineTimersRef.current = [];
    setPipelineStep(0);
    setPipelineError(false);
    const go = (step, ms) => pipelineTimersRef.current.push(setTimeout(() => setPipelineStep(step), ms));
    go(1, 1500); go(2, 4000); go(3, 8500); go(4, 17000); go(5, 23000);
  };

  const finishPipelineAnim = (success) => {
    pipelineTimersRef.current.forEach(t => clearTimeout(t));
    pipelineTimersRef.current = [];
    if (success) {
      setPipelineStep(6);
      pipelineTimersRef.current.push(setTimeout(() => setPipelineStep(-1), 5000));
    } else {
      setPipelineError(true);
      pipelineTimersRef.current.push(setTimeout(() => { setPipelineStep(-1); setPipelineError(false); }, 3500));
    }
  };

  useEffect(() => () => { pipelineTimersRef.current.forEach(t => clearTimeout(t)); }, []);

  const MAX_UPLOAD_SIZE_BYTES = 50000 * 1024;
  const ALLOWED_UPLOAD_EXTENSIONS = new Set(['txt', 'md', 'csv', 'json', 'xml', 'xlsx', 'pdf']);

  const fetchFiles = useCallback(async () => {
    try {
      const res = await apiFetch('/api/admin/sources', apiKey);
      setFiles(res.files);
    } catch(e) {} finally { setLoading(false); }
  }, [apiKey]);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  useEffect(() => {
    const preventBrowserDrop = (e) => {
      // Empêche le navigateur d'ouvrir le fichier déposé hors de la zone d'upload.
      e.preventDefault();
    };

    window.addEventListener('dragover', preventBrowserDrop);
    window.addEventListener('drop', preventBrowserDrop);
    return () => {
      window.removeEventListener('dragover', preventBrowserDrop);
      window.removeEventListener('drop', preventBrowserDrop);
    };
  }, []);

  const handleDelete = async (filename) => {
    try {
      if(!MOCK_MODE) {
        const res = await apiFetch('/api/admin/delete', apiKey, { method: 'DELETE', body: JSON.stringify({ filename }) });
        const details = res.ingestion?.summary ? ` ${res.ingestion.summary}` : '';
        setUploadMsg({ ok: true, text: `${res.message || 'Fichier supprimé.'}${details}`.trim() });
        await fetchFiles();
      } else {
        setFiles(f => f.filter(name => name !== filename));
        setUploadMsg({ ok: true, text: 'Fichier supprimé.' });
      }
    } catch (e) {
      setUploadMsg({ ok: false, text: e.message || 'Suppression impossible.' });
    }
  };

  const openReplacePicker = (filename) => {
    replaceTargetRef.current = filename;
    setReplaceTarget(filename);
    if (replaceInputRef.current) {
      // Important: reset value so selecting the same file still triggers onChange.
      replaceInputRef.current.value = '';
      replaceInputRef.current.dataset.targetFilename = filename;
    }
    ignoreNextUploadZoneClickRef.current = true;
    setUploadMsg({ ok: true, text: `Sélectionne le fichier de remplacement pour '${filename}'.` });
    replaceInputRef.current?.click();
  };

  const validateUploadFile = (file) => {
    if (!file) return { ok: false, error: 'Aucun fichier sélectionné.' };
    const name = (file.name || '').trim();
    if (!name || name.includes('..') || /[\\/]/.test(name)) {
      return { ok: false, error: 'Nom de fichier invalide.' };
    }

    const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
    if (!ALLOWED_UPLOAD_EXTENSIONS.has(ext)) {
      return { ok: false, error: 'Extension non supportée.' };
    }

    if (!file.size || file.size > MAX_UPLOAD_SIZE_BYTES) {
      return { ok: false, error: 'Fichier vide ou trop volumineux (max 500 Ko).' };
    }

    return { ok: true };
  };

  const handleUpload = async (file) => {
    if (!file) return;
    const check = validateUploadFile(file);
    if (!check.ok) {
      setUploadMsg({ ok: false, text: check.error });
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    startPipelineAnim();
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/admin/upload', {
        method: 'POST',
        headers: { 'X-Monitoring-Key': apiKey },
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        const details = data.ingestion?.summary ? ` ${data.ingestion.summary}` : '';
        setUploadMsg({ ok: true, text: `${data.message || 'Fichier uploadé !'}${details}`.trim() });
        fetchFiles();
        finishPipelineAnim(true);
      } else {
        setUploadMsg({ ok: false, text: data.error || 'Erreur upload.' });
        finishPipelineAnim(false);
      }
    } catch(e) {
      setUploadMsg({ ok: false, text: 'Erreur réseau.' });
      finishPipelineAnim(false);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.stopPropagation();
    e.preventDefault();
    setDragging(false);

    const items = Array.from(e.dataTransfer?.items || []);
    const files = Array.from(e.dataTransfer?.files || []);
    if (items.length && items.some((item) => item.kind !== 'file')) {
      setUploadMsg({ ok: false, text: 'Dépose uniquement des fichiers.' });
      return;
    }
    if (files.length !== 1) {
      setUploadMsg({ ok: false, text: 'Dépose un seul fichier à la fois.' });
      return;
    }

    const file = files[0];
    if (file) handleUpload(file);
  };

  const handleReindex = async () => {
    setReindexing(true);
    if(!MOCK_MODE) {
      try { await apiFetch('/api/reindex', apiKey, { method: 'POST', body: JSON.stringify({ force: true }) }); } catch(e){}
    } else {
      await new Promise(r => setTimeout(r, 2000));
    }
    setReindexing(false);
  };

  const handleReplace = async (file, targetFilename) => {
    if (!file) {
      // User closed the picker without selecting a file.
      return;
    }
    const effectiveTarget = targetFilename || replaceTargetRef.current;
    if (!effectiveTarget) {
      setUploadMsg({ ok: false, text: 'Fichier cible introuvable pour le remplacement.' });
      return;
    }
    const check = validateUploadFile(file);
    if (!check.ok) {
      setUploadMsg({ ok: false, text: check.error });
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    startPipelineAnim();
    try {
      const formData = new FormData();
      // Reuse /upload upsert path and force the backend-visible filename.
      formData.append('file', file, effectiveTarget);

      const res = await fetch('/api/admin/upload', {
        method: 'POST',
        headers: { 'X-Monitoring-Key': apiKey },
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        const details = data.ingestion?.summary ? ` ${data.ingestion.summary}` : '';
        setUploadMsg({ ok: true, text: `${data.message || 'Fichier remplacé !'}${details}`.trim() });
        await fetchFiles();
        finishPipelineAnim(true);
      } else {
        setUploadMsg({ ok: false, text: data.error || 'Erreur remplacement.' });
        finishPipelineAnim(false);
      }
    } catch (e) {
      setUploadMsg({ ok: false, text: 'Erreur réseau.' });
      finishPipelineAnim(false);
    } finally {
      setUploading(false);
      setReplaceTarget('');
      replaceTargetRef.current = '';
      if (replaceInputRef.current) {
        replaceInputRef.current.value = '';
        replaceInputRef.current.dataset.targetFilename = '';
      }
      // Ignore one accidental click on the upload zone when the OS file picker closes.
      setTimeout(() => {
        ignoreNextUploadZoneClickRef.current = false;
      }, 100);
    }
  };

  const getExtColor = (ext) => {
    switch(ext) {
      case 'md': return 'text-purple-400 border-purple-400/20 bg-purple-400/10';
      case 'pdf': return 'text-red-400 border-red-400/20 bg-red-400/10';
      case 'csv': return 'text-green-400 border-green-400/20 bg-green-400/10';
      case 'json': return 'text-yellow-400 border-yellow-400/20 bg-yellow-400/10';
      default: return 'text-blue-400 border-blue-400/20 bg-blue-400/10';
    }
  };

  return (
    <>
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <Card delay={0} className="xl:col-span-2 h-[500px] flex flex-col">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-white/40 text-xs uppercase tracking-widest">Fichiers Indexés ({files.length})</h3>
          <button onClick={handleReindex} disabled={reindexing} className="flex items-center gap-2 px-4 py-2 rounded-full text-[10px] uppercase tracking-widest font-bold bg-[#5ed29c]/10 text-[#5ed29c] hover:bg-[#5ed29c]/20 transition-colors disabled:opacity-50">
            <RefreshCw size={12} className={reindexing ? 'animate-spin' : ''} /> {reindexing ? 'Re-indexation...' : 'Forcer Re-indexation'}
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-2">
          {loading ? [1,2,3].map(i => <Skeleton key={i} className="h-12 w-full" />) : files.map((file, i) => {
            const ext = file.split('.').pop().toLowerCase();
            return (
              <motion.div key={file} initial={{opacity:0, x:-10}} animate={{opacity:1, x:0}} transition={{delay: i*0.05}} className="flex items-center justify-between p-3 rounded-xl border border-white/5 bg-white/[0.01] hover:bg-white/5 transition-colors group">
                <div className="flex items-center gap-4">
                  <span className={`text-[10px] uppercase font-bold px-2 py-1 rounded border ${getExtColor(ext)}`}>{ext}</span>
                  <span className="text-sm text-white/80">{file}</span>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); openReplacePicker(file); }}
                    className="p-2 text-white/20 hover:text-[#5ed29c] transition-colors"
                    title="Modifier ce fichier"
                  >
                    <Pencil size={16} />
                  </button>
                  <button
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleDelete(file); }}
                    className="p-2 text-white/20 hover:text-[#f87171] transition-colors"
                    title="Supprimer ce fichier"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </motion.div>
            )
          })}
        </div>
      </Card>

      <Card delay={0.1}
        className={`flex flex-col items-center justify-center border-dashed border-2 transition-colors cursor-pointer group text-center py-12 ${dragging ? 'border-[#5ed29c] bg-[#5ed29c]/5' : 'border-white/10 hover:border-[#5ed29c]/50'}`}
        onClick={() => {
          if (ignoreNextUploadZoneClickRef.current) return;
          fileInputRef.current?.click();
        }}
        onDragEnter={(e) => { e.stopPropagation(); e.preventDefault(); setDragging(true); }}
        onDragOver={(e) => { e.stopPropagation(); e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; setDragging(true); }}
        onDragLeave={(e) => { e.stopPropagation(); e.preventDefault(); setDragging(false); }}
        onDrop={handleDrop}
      >
        <input ref={fileInputRef} type="file" accept=".txt,.md,.csv,.json,.xml,.xlsx,.pdf" className="hidden"
          onChange={(e) => handleUpload(e.target.files[0])} />
        <input
          ref={replaceInputRef}
          type="file"
          accept=".txt,.md,.csv,.json,.xml,.xlsx,.pdf"
          className="hidden"
          onChange={(e) => handleReplace(e.target.files[0], e.target.dataset.targetFilename || replaceTargetRef.current || replaceTarget)}
        />
        <div className={`p-4 rounded-full mb-4 transition-colors ${dragging ? 'bg-[#5ed29c]/20' : 'bg-white/5 group-hover:bg-[#5ed29c]/10'}`}>
          <UploadCloud size={32} className={`transition-colors ${dragging ? 'text-[#5ed29c]' : 'text-white/40 group-hover:text-[#5ed29c]'}`} />
        </div>
        <h4 className="text-lg font-serif-italic mb-2">
          {uploading ? 'Upload en cours...' : 'Ajouter un document'}
        </h4>
        <p className="text-xs text-white/40 px-6">
          {dragging ? 'Relâchez pour uploader' : 'Glissez-déposez vos fichiers ici ou cliquez pour parcourir.'}
        </p>
        {uploadMsg && (
          <div className={`mt-4 text-xs px-4 py-2 rounded-lg ${uploadMsg.ok ? 'text-[#5ed29c] bg-[#5ed29c]/10' : 'text-[#f87171] bg-[#f87171]/10'}`}>
            {uploadMsg.text}
          </div>
        )}
        <div className="text-[10px] text-white/20 uppercase tracking-widest mt-4">.txt, .md, .csv, .json, .xml, .xlsx, .pdf</div>
      </Card>
    </div>
    <div className="mt-6">
      <IngestionFlowVis currentStep={pipelineStep} hasError={pipelineError} />
    </div>
    </>
  );
};

// 5. LOGS
const LogsTab = ({ apiKey }) => {
  const [logs, setLogs] = useState([]);
  const [paused, setPaused] = useState(false);
  const scrollRef = useRef(null);

  const fetchLogs = useCallback(async () => {
    if (paused) return;
    try {
      const res = await apiFetch('/api/monitoring/logs', apiKey);
      setLogs(res.logs);
    } catch(e) {}
  }, [apiKey, paused]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);
  useInterval(fetchLogs, 5000); // refresh plus rapide pour logs

  useEffect(() => {
    if (!paused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, paused]);

  const getColor = (lvl) => {
    switch(lvl) {
      case 'ERROR': return 'text-[#f87171]';
      case 'WARNING': return 'text-[#fb923c]';
      case 'DEBUG': return 'text-white/30';
      default: return 'text-white/70';
    }
  };

  return (
    <Card delay={0} className="flex flex-col h-[600px] p-0 overflow-hidden bg-[#0a0a0a]">
      {/* Terminal Toolbar */}
      <div className="flex justify-between items-center px-4 py-3 border-b border-white/10 bg-black/40">
        <div className="flex items-center gap-2">
          <TerminalSquare size={16} className="text-white/40" />
          <span className="text-xs uppercase tracking-widest text-white/40 font-mono-custom">System.out</span>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setPaused(!paused)} className="p-1.5 rounded bg-white/5 hover:bg-white/10 text-white/60 transition-colors">
            {paused ? <Play size={14} /> : <Pause size={14} />}
          </button>
        </div>
      </div>
      
      {/* Terminal Output */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto custom-scrollbar p-4 font-mono-custom text-xs space-y-1.5">
        {logs.map((log, i) => (
          <div key={i} className="flex gap-4 hover:bg-white/5 px-2 py-0.5 rounded transition-colors">
            <span className="text-white/30 shrink-0">[{log.time}]</span>
            <span className={`w-16 shrink-0 ${getColor(log.level)}`}>{log.level}</span>
            <span className="text-[#60a5fa] shrink-0">[{log.name}]</span>
            <span className="text-white/80">{log.msg}</span>
          </div>
        ))}
      </div>
    </Card>
  );
};

// ============================================================================
// PAGE PRINCIPALE & WRAPPER AUTH
// ============================================================================

const MonitoringPage = ({ apiKey, onLogout }) => {
  const tabs = ['Vue d\'ensemble', 'Features', 'Sources', 'Logs'];
  const [activeTab, setActiveTab] = useState(tabs[0]);
  const navigate = useNavigate();

  const renderTab = () => {
    switch(activeTab) {
      case tabs[0]: return <OverviewTab apiKey={apiKey} />;
      case tabs[1]: return <FeatureGridTab apiKey={apiKey} />;
      case tabs[2]: return <SourcesTab apiKey={apiKey} />;
      case tabs[3]: return <LogsTab apiKey={apiKey} />;
      default: return null;
    }
  };

  return (
    <div className="admin-root flex flex-col">
      {/* Navbar Admin */}
      <nav className="sticky top-0 z-50 bg-black/80 backdrop-blur-md border-b border-white/10 px-6 py-4">
        <div className="max-w-[1400px] mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-3 hover:opacity-80 transition-opacity"
          >
            <span className="text-2xl font-serif-italic text-white tracking-tight">DocOracle</span>
            <span className="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest bg-[#5ed29c] text-black">Admin</span>
            {MOCK_MODE && <span className="px-2 py-0.5 rounded border border-[#fb923c] text-[#fb923c] text-[9px] uppercase tracking-widest">Mock Mode</span>}
          </button>

          <div className="flex bg-white/5 rounded-full p-1">
            {tabs.map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`relative px-5 py-2 text-xs uppercase tracking-widest transition-colors ${activeTab === tab ? 'text-white font-medium' : 'text-white/40 hover:text-white/70'}`}
              >
                {activeTab === tab && (
                  <motion.div layoutId="active-tab" className="absolute inset-0 bg-white/10 rounded-full" transition={{ type: "spring", duration: 0.5 }} />
                )}
                <span className="relative z-10">{tab}</span>
              </button>
            ))}
          </div>

          <button onClick={onLogout} className="text-xs uppercase tracking-widest text-[#f87171] hover:bg-[#f87171]/10 px-4 py-2 rounded-full transition-colors">
            Déconnexion
          </button>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 max-w-[1400px] w-full mx-auto p-6 md:p-10">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {renderTab()}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
};

export default function MonitoringRoute() {
  const [apiKey, setApiKey] = useState(sessionStorage.getItem('lk_monitor_key'));
  const [inputKey, setInputKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await apiFetch('/api/monitoring/stats', inputKey); // Test de la clé (endpoint protégé)
      sessionStorage.setItem('lk_monitor_key', inputKey);
      setApiKey(inputKey);
    } catch(err) {
      setError("Accès refusé. Clé de monitoring invalide.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('lk_monitor_key');
    setApiKey(null);
  };

  if (apiKey) {
    return (
      <>
        <style dangerouslySetInnerHTML={{ __html: styles }} />
        <MonitoringPage apiKey={apiKey} onLogout={handleLogout} />
      </>
    );
  }

  return (
    <div className="admin-root flex items-center justify-center p-6 relative">
      <style dangerouslySetInnerHTML={{ __html: styles }} />
      {/* Background pattern */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-white/[0.03] via-black to-black pointer-events-none" />
      
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="liquid-glass rounded-[32px] p-10 w-full max-w-sm relative z-10 border border-white/10 shadow-2xl">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-serif-italic mb-2">Accès Monitoring</h1>
          <p className="text-xs text-white/40 uppercase tracking-widest">DocOracle — Monitoring v4.2</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div className="space-y-2">
            <div className="liquid-glass bg-black/40 rounded-full px-6 py-4 border border-white/5 focus-within:border-[#5ed29c]/50 transition-colors">
              <input
                type="password"
                placeholder="Clé de monitoring..."
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                className="w-full bg-transparent border-none outline-none text-white text-sm font-mono-custom placeholder:text-white/20 placeholder:font-sans"
                autoFocus
              />
            </div>
            {error && <motion.p initial={{opacity:0}} animate={{opacity:1}} className="text-[#f87171] text-xs px-4">{error}</motion.p>}
          </div>

          <button disabled={loading || !inputKey} className="w-full bg-white text-black font-bold py-4 rounded-full hover:scale-[1.02] active:scale-95 transition-all text-xs uppercase tracking-widest shadow-xl disabled:opacity-50 disabled:hover:scale-100">
            {loading ? 'Vérification...' : 'Accéder au système'}
          </button>
        </form>
        {MOCK_MODE && <p className="text-center text-[10px] text-[#fb923c] mt-6 uppercase tracking-widest">Mock mode actif (Clé: lorekeeper2026)</p>}
      </motion.div>
    </div>
  );
}