import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion'; // motion used in FeatureCard expand/collapse
import {
  Search, Brain, Layers, Shield, Zap, BarChart3, Database,
  GitBranch, CheckCircle, XCircle, ChevronRight, Users, BookOpen,
  Lightbulb, Cpu, Lock, Clock, ArrowUpRight, Code2, Sparkles, Server
} from 'lucide-react';

const VIDEO_BG = "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4";

const SECTIONS = [
  { id: 'features', label: 'Fonctionnalités', icon: Sparkles },
  { id: 'stack', label: 'Stack & Choix', icon: Cpu },
  { id: 'team', label: "L'équipe", icon: Users },
  { id: 'learned', label: 'Ce qu\'on a appris', icon: Lightbulb },
];

// ── Fade-in on scroll ────────────────────────────────────────────────────────
const FadeIn = ({ children, className = '' }) => (
  <div className={className}>{children}</div>
);

// ── Section header ───────────────────────────────────────────────────────────
const SectionHeader = ({ eyebrow, title, subtitle }) => (
  <div className="mb-14">
    <div className="text-[9px] uppercase tracking-[0.35em] text-[#F59E0B]/60 mb-4 font-mono">{eyebrow}</div>
    <h2 className="text-4xl md:text-6xl font-serif-custom tracking-tighter text-white leading-[0.95] mb-5">{title}</h2>
    {subtitle && <p className="text-white/35 text-base max-w-2xl leading-relaxed">{subtitle}</p>}
  </div>
);

// ── Feature card ─────────────────────────────────────────────────────────────
const FeatureCard = ({ icon: Icon, color, title, what, how, params, delay }) => {
  const [open, setOpen] = useState(false);
  return (
    <FadeIn delay={delay}>
      <div
        className="rounded-[24px] border border-white/[0.07] overflow-hidden transition-all duration-300 cursor-pointer hover:border-white/[0.12]"
        style={{ background: 'rgba(255,255,255,0.02)' }}
        onClick={() => setOpen(o => !o)}
      >
        <div className="p-6 flex items-start gap-5">
          <div className="w-11 h-11 rounded-[14px] flex items-center justify-center shrink-0"
            style={{ background: `${color}12`, border: `1px solid ${color}25` }}>
            <Icon size={18} style={{ color }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-4">
              <h3 className="text-[15px] font-semibold text-white">{title}</h3>
              <motion.div animate={{ rotate: open ? 90 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronRight size={14} className="text-white/25 shrink-0" />
              </motion.div>
            </div>
            <p className="text-[12px] text-white/40 mt-1 leading-relaxed">{what}</p>
          </div>
        </div>
        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <div className="px-6 pb-6 border-t border-white/[0.05] pt-5 space-y-4">
                <div>
                  <div className="text-[9px] uppercase tracking-[0.3em] text-white/25 mb-2">Implémentation</div>
                  <p className="text-[12px] text-white/55 leading-relaxed">{how}</p>
                </div>
                {params && (
                  <div>
                    <div className="text-[9px] uppercase tracking-[0.3em] text-white/25 mb-2">Paramètres clés</div>
                    <div className="flex flex-wrap gap-2">
                      {params.map(p => (
                        <span key={p} className="px-2.5 py-1 rounded-full text-[10px] font-mono border border-white/[0.08]"
                          style={{ background: `${color}08`, color: `${color}CC` }}>{p}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </FadeIn>
  );
};

// ── Tech comparison row ───────────────────────────────────────────────────────
const TechRow = ({ category, chosen, alternatives, why, delay }) => (
  <FadeIn delay={delay}>
    <div className="rounded-[20px] border border-white/[0.06] p-6" style={{ background: 'rgba(255,255,255,0.015)' }}>
      <div className="flex flex-col md:flex-row md:items-start gap-5">
        <div className="md:w-32 shrink-0">
          <div className="text-[8px] uppercase tracking-[0.3em] text-white/25 mb-1">Domaine</div>
          <div className="text-[11px] font-semibold text-white/60">{category}</div>
        </div>
        <div className="flex-1 grid md:grid-cols-3 gap-4">
          <div>
            <div className="text-[8px] uppercase tracking-[0.3em] text-[#F59E0B]/50 mb-2">Choisi</div>
            <div className="flex items-center gap-2">
              <CheckCircle size={12} className="text-[#F59E0B] shrink-0" />
              <span className="text-[13px] font-semibold text-white">{chosen}</span>
            </div>
          </div>
          <div>
            <div className="text-[8px] uppercase tracking-[0.3em] text-white/25 mb-2">Alternatives</div>
            <div className="flex items-center gap-2">
              <XCircle size={12} className="text-white/20 shrink-0" />
              <span className="text-[12px] text-white/35">{alternatives}</span>
            </div>
          </div>
          <div>
            <div className="text-[8px] uppercase tracking-[0.3em] text-white/25 mb-2">Pourquoi</div>
            <p className="text-[11px] text-white/50 leading-relaxed">{why}</p>
          </div>
        </div>
      </div>
    </div>
  </FadeIn>
);

// ── Team card ─────────────────────────────────────────────────────────────────
const TeamCard = ({ name, role, tasks, delay }) => (
  <FadeIn delay={delay}>
    <div className="rounded-[24px] border border-white/[0.06] p-7 h-full" style={{ background: 'rgba(255,255,255,0.02)' }}>
      <div className="w-10 h-10 rounded-full flex items-center justify-center font-serif-custom italic text-lg text-[#F59E0B] border border-[#F59E0B]/20 mb-5"
        style={{ background: 'rgba(245,158,11,0.06)' }}>
        {name[0]}
      </div>
      <h3 className="text-[17px] font-serif-custom italic text-white mb-1">{name}</h3>
      <div className="text-[9px] uppercase tracking-[0.25em] text-[#F59E0B]/50 mb-4">{role}</div>
      <ul className="space-y-2">
        {tasks.map((t, i) => (
          <li key={i} className="flex items-start gap-2 text-[12px] text-white/40">
            <span className="text-[#F59E0B]/40 mt-0.5 shrink-0">—</span>{t}
          </li>
        ))}
      </ul>
    </div>
  </FadeIn>
);

// ── Lesson card ───────────────────────────────────────────────────────────────
const LessonCard = ({ number, title, content, delay }) => (
  <FadeIn delay={delay}>
    <div className="flex gap-6">
      <div className="text-[40px] font-serif-custom italic text-white/[0.06] leading-none shrink-0 select-none">
        {String(number).padStart(2, '0')}
      </div>
      <div className="pt-1 pb-8 border-b border-white/[0.05]">
        <h4 className="text-[15px] font-semibold text-white mb-2">{title}</h4>
        <p className="text-[12px] text-white/45 leading-relaxed">{content}</p>
      </div>
    </div>
  </FadeIn>
);

// ── Main page ─────────────────────────────────────────────────────────────────
export default function DocsPage() {
  const [active, setActive] = useState('features');
  const sectionRefs = useRef({});

  const scrollTo = (id) => {
    sectionRefs.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setActive(id);
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(e => { if (e.isIntersecting) setActive(e.target.id); });
      },
      { rootMargin: '-30% 0px -60% 0px' }
    );
    Object.values(sectionRefs.current).forEach(el => el && observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const FEATURES = [
    {
      icon: Search, color: '#F59E0B', title: 'Recherche Hybride BM25 + Vector',
      what: 'Double moteur de recherche fusionné par Reciprocal Rank Fusion pour un rappel maximal.',
      how: 'BM25 (Elasticsearch-style) capture les correspondances exactes de tokens. L\'embedding dense via FastEmbed (BAAI/bge-small-en-v1.5) capture la sémantique. Les scores sont normalisés puis fusionnés : score_final = Σ 1/(k + rank_i) avec k=60.',
      params: ['top_k=10', 'RRF k=60', 'bge-small-en-v1.5', 'Qdrant'],
    },
    {
      icon: Brain, color: '#60a5fa', title: 'Reformulation Contextuelle',
      what: 'Résout les anaphores et références implicites dans les questions de suivi.',
      how: 'Si la question contient des pronoms ("il", "elle", "ça", "ce truc") ou des références floues, un LLM Groq léger (llama3-8b-8192) reformule la question en 150–300ms en intégrant l\'historique des 3 derniers échanges. Le résultat est injecté dans la recherche à la place de la question brute.',
      params: ['llama3-8b-8192', 'Groq', 'max_history=3', '< 300ms'],
    },
    {
      icon: Layers, color: '#a78bfa', title: 'Re-ranking Cross-Encoder',
      what: 'Réordonne les passages récupérés par pertinence réelle plutôt que par score vectoriel.',
      how: 'Après la fusion RRF, un cross-encoder (ms-marco-MiniLM-L-6-v2) réévalue chaque passage face à la question. Il est intelligent : si le score top-1 dépasse 0.85, le reranker est sauté pour économiser 100–200ms. Sinon, il réordonne et garde les top-5.',
      params: ['ms-marco-MiniLM-L-6-v2', 'threshold=0.85', 'top_k=5', 'smart_skip'],
    },
    {
      icon: Shield, color: '#f87171', title: 'Sécurité & PII',
      what: 'Double couche : regex PII + juge LLM contre hallucinations et injections de prompt.',
      how: 'Layer 1 : regex anti-PII retire emails, numéros de téléphone, IBAN des réponses avant envoi. Layer 2 : un juge LLM autonome évalue si la réponse est (a) ancrée dans les sources, (b) hors-sujet, (c) injection de prompt. En option, Lakera Guard surveille les jailbreaks via API externe.',
      params: ['PII regex', 'LLM judge', 'Lakera Guard', 'fail-open'],
    },
    {
      icon: Zap, color: '#fbbf24', title: 'Streaming Multi-LLM avec Fallback',
      what: 'Tokens en temps réel via SSE avec basculement automatique sur 4 niveaux de LLM.',
      how: 'Le LLM principal est servi via OpenRouter (modèle configurable). Sur erreur 429 ou timeout, la chaîne bascule sur Groq (mixtral-8x7b), puis OpenRouter-gratuit, puis réponse d\'urgence statique. Le stream SSE ne s\'interrompt pas — le client ne voit jamais l\'erreur sous-jacente.',
      params: ['OpenRouter', 'Groq', 'SSE', '4 fallbacks'],
    },
    {
      icon: BarChart3, color: '#34d399', title: 'Observabilité Langfuse',
      what: 'Traçage complet de chaque requête : latence, modèle, fallbacks, score juge, feedback.',
      how: 'Chaque requête crée un "trace" Langfuse avec spans imbriqués : reformulation, search, rerank, generation. Les feedbacks 👍/👎 sont pushés via l\'API score. Un résumé LLM de l\'historique long-terme est généré tous les 10 échanges et stocké dans Qdrant comme mémoire utilisateur.',
      params: ['Langfuse traces', 'spans', 'score API', 'mémoire LLM'],
    },
  ];

  const STACK = [
    { category: 'Vector DB', chosen: 'Qdrant', alternatives: 'Pinecone, Weaviate, Chroma', why: 'Open-source, auto-hébergeable, filtres payload, performance native Rust. Pinecone est trop cher pour un projet étudiant.', delay: 0 },
    { category: 'LLM Principal', chosen: 'OpenRouter (multi-modèle)', alternatives: 'OpenAI GPT-4, Mistral, Claude', why: 'OpenRouter centralise les accès LLM, gère les fallbacks automatiques et permet de changer de modèle sans modifier le code. Coût maîtrisé vs appel direct GPT-4.', delay: 0.05 },
    { category: 'LLM Rapide', chosen: 'Groq (llama3)', alternatives: 'Ollama local, Together AI', why: 'Latence < 150ms vs 800ms local. Idéal pour reformulation où la vitesse prime sur la qualité.', delay: 0.1 },
    { category: 'Tracing', chosen: 'Langfuse', alternatives: 'LangSmith, Helicone, Arize', why: 'Open-source, RGPD-friendly, SDK Python first-class, self-hostable. LangSmith est propriétaire et coûteux.', delay: 0.15 },
    { category: 'Auth', chosen: 'Supabase', alternatives: 'Firebase, Auth0, Clerk', why: 'PostgreSQL sous le capot, open-source, SDK JavaScript simple, OAuth intégré (GitHub, Google).', delay: 0.2 },
    { category: 'Cache', chosen: 'Redis + Semantic Cache', alternatives: 'Memcached, in-memory', why: 'Cache sémantique custom : les questions similaires (cosine > 0.92) renvoient la réponse en cache sans appel LLM.', delay: 0.25 },
    { category: 'Backend', chosen: 'FastAPI', alternatives: 'Flask, Django, Express', why: 'Async natif pour le streaming SSE, auto-documentation OpenAPI, Pydantic pour la validation.', delay: 0.3 },
    { category: 'Embedding', chosen: 'FastEmbed (bge-small)', alternatives: 'OpenAI text-embedding-3, Cohere', why: 'Zéro coût, zéro latence réseau, tourne en local. 384 dimensions suffisent pour le lore.', delay: 0.35 },
    { category: 'Conteneurisation', chosen: 'Docker + Compose', alternatives: 'Podman, K8s, bare metal', why: 'Docker Compose orchestre FastAPI, Qdrant, Redis et Nginx en un seul fichier. Reproductible en local et en prod sans configuration supplémentaire.', delay: 0.4 },
  ];

  const TEAM = [
    { name: 'Emir', role: 'Lead Fullstack & Architecture', tasks: ['Architecture globale du système RAG', 'Frontend React (landing, chat, monitoring)', 'Pipeline de recherche hybride BM25 + Vector', 'Déploiement Docker & CI/CD'], delay: 0 },
    { name: 'Ediz', role: 'Backend & Ingestion', tasks: ['Pipeline d\'ingestion multi-format', 'Chunking contextuel et enrichissement', 'Watchdog de réindexation automatique', 'Tests unitaires ingestion'], delay: 0.08 },
    { name: 'Nicolas', role: 'Sécurité & Observabilité', tasks: ['Implémentation Langfuse tracing', 'Juge LLM anti-hallucination', 'PII masking et intégration Lakera', 'Dashboard monitoring'], delay: 0.16 },
    { name: 'Tom', role: 'Recherche & Évaluation', tasks: ['Benchmarks BM25 vs Vector vs Hybrid', 'Tuning re-ranking cross-encoder', 'HyDE fallback implementation', 'Évaluation qualitative des réponses'], delay: 0.24 },
  ];

  const LESSONS = [
    { title: 'Le RAG est plus dur que prévu', content: 'On pensait que brancher un LLM sur des documents serait simple. En réalité, la qualité dépend massivement du chunking, de la stratégie de recherche et du prompt. Un mauvais chunking casse tout même avec un bon LLM.', delay: 0 },
    { title: 'La recherche hybride bat la recherche pure', content: 'BM25 seul rate les synonymes. Vector seul rate les noms propres et termes techniques. RRF hybride améliore le rappel de ~25% sur notre corpus de lore. Aucun des deux moteurs seul ne suffit.', delay: 0.06 },
    { title: 'Les fallbacks sont indispensables en prod', content: 'Les LLM ont une disponibilité variable. Sans les 4 niveaux de fallback (LLM principal → Groq → OpenRouter-free → statique), le système aurait été indisponible plusieurs fois. Le design "fail gracefully" est non-négociable.', delay: 0.12 },
    { title: 'L\'observabilité change tout', content: 'Sans Langfuse, on déboguait à l\'aveugle. Les traces ont révélé que 40% des lenteurs venaient du re-ranking, pas du LLM — ce qui a motivé l\'ajout du smart skip. L\'observabilité n\'est pas un bonus, c\'est une nécessité.', delay: 0.18 },
    { title: 'Le streaming SSE améliore drastiquement l\'UX', content: 'Même si le LLM met 3 secondes à répondre, le stream token-par-token crée une perception de rapidité. Les utilisateurs restent engagés. Sans streaming, une attente de 3s semble éternelle.', delay: 0.24 },
    { title: 'Le cache sémantique est sous-estimé', content: 'Notre cache Redis avec seuil cosine 0.92 réduit de ~30% les appels LLM sur les questions récurrentes (personnages principaux, factions). C\'est une optimisation coût/performance à déployer dès le début.', delay: 0.3 },
  ];

  return (
    <div className="min-h-screen text-white font-body relative">
      {/* Video background — désactivée (garder pour réactiver) */}
      {/* <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <video className="absolute inset-0 w-full h-full object-cover opacity-25 mix-blend-screen"
          src={VIDEO_BG} muted autoPlay loop playsInline />
        <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/50 to-black/80" />
      </div> */}

      {/* Content */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 pt-36 pb-32">

        {/* Page hero */}
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }} className="mb-20">
          <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full border border-white/[0.07]" style={{ background: 'rgba(245,158,11,0.04)' }}>
            <BookOpen size={10} className="text-[#F59E0B]" />
            <span className="text-[9px] uppercase tracking-[0.3em] text-[#F59E0B]/70">Documentation</span>
          </div>
          <h1 className="text-6xl md:text-8xl font-serif-custom tracking-tighter text-white leading-[0.9] mb-6">
            L'Oracle,<br /><em className="italic text-white/35">de l'intérieur.</em>
          </h1>
          <p className="text-white/35 text-base max-w-xl leading-relaxed">
            Tout ce que vous devez savoir sur le fonctionnement de LoreKeeper — features, choix techniques, équipe et leçons apprises.
          </p>
        </motion.div>

        {/* Layout : sidebar + content */}
        <div className="flex gap-12 items-start">

          {/* Sticky sidebar */}
          <aside className="hidden lg:block w-52 shrink-0 sticky top-28">
            <nav className="space-y-1">
              {SECTIONS.map(({ id, label, icon: Icon }) => (
                <button key={id} onClick={() => scrollTo(id)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all group"
                  style={{ background: active === id ? 'rgba(245,158,11,0.08)' : 'transparent', borderLeft: active === id ? '2px solid #F59E0B' : '2px solid transparent' }}>
                  <Icon size={13} style={{ color: active === id ? '#F59E0B' : 'rgba(255,255,255,0.25)' }} />
                  <span className="text-[11px] uppercase tracking-[0.15em] font-medium" style={{ color: active === id ? '#F59E0B' : 'rgba(255,255,255,0.35)' }}>{label}</span>
                </button>
              ))}
            </nav>
          </aside>

          {/* Main content */}
          <main className="flex-1 min-w-0 space-y-28">

            {/* ── FEATURES ─────────────────────────────────────── */}
            <section id="features" ref={el => sectionRefs.current.features = el}>
              <SectionHeader
                eyebrow="Fonctionnalités"
                title="Ce que fait LoreKeeper."
                subtitle="Six composants RAG qui s'enchaînent pour produire des réponses précises, ancrées dans vos données et jamais inventées. Cliquez sur une feature pour voir l'implémentation."
              />
              <div className="space-y-3">
                {FEATURES.map((f, i) => <FeatureCard key={f.title} {...f} delay={i * 0.05} />)}
              </div>
            </section>

            {/* ── STACK ────────────────────────────────────────── */}
            <section id="stack" ref={el => sectionRefs.current.stack = el}>
              <SectionHeader
                eyebrow="Stack & Choix Techniques"
                title="Pourquoi ces outils."
                subtitle="Chaque outil a été évalué contre ses alternatives. Voici nos décisions et les raisons qui les justifient."
              />
              <div className="space-y-3">
                {STACK.map((s, i) => <TechRow key={s.category} {...s} delay={i * 0.04} />)}
              </div>
            </section>

            {/* ── TEAM ─────────────────────────────────────────── */}
            <section id="team" ref={el => sectionRefs.current.team = el}>
              <SectionHeader
                eyebrow="L'équipe"
                title="Les LoreKeepers."
                subtitle="Quatre étudiants, une vision. Chacun a pris en charge un domaine du système avec une ownership complète."
              />
              <div className="grid md:grid-cols-2 gap-4">
                {TEAM.map(m => <TeamCard key={m.name} {...m} />)}
              </div>

              {/* Collab tools */}
              <FadeIn delay={0.3}>
                <div className="mt-8 rounded-[24px] border border-white/[0.06] p-7" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div className="text-[9px] uppercase tracking-[0.3em] text-white/25 mb-4">Outils de collaboration</div>
                  <div className="flex flex-wrap gap-3">
                    {[
                      { name: 'GitHub', desc: 'Versionning & PR reviews' },
                      { name: 'Discord', desc: 'Communication & daily sync' },
                      { name: 'Obsidian', desc: 'Documentation & planning' },
                      { name: 'Docker', desc: 'Conteneurisation & déploiement' },
                      { name: 'Postman', desc: 'Tests API manuels' },
                      { name: 'Langfuse', desc: 'Monitoring RAG partagé' },
                    ].map(t => (
                      <div key={t.name} className="flex items-center gap-2 px-4 py-2.5 rounded-full border border-white/[0.07]"
                        style={{ background: 'rgba(255,255,255,0.02)' }}>
                        <span className="text-[12px] font-semibold text-white">{t.name}</span>
                        <span className="text-[10px] text-white/25">—</span>
                        <span className="text-[10px] text-white/40">{t.desc}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </FadeIn>
            </section>

            {/* ── LEARNED ──────────────────────────────────────── */}
            <section id="learned" ref={el => sectionRefs.current.learned = el}>
              <SectionHeader
                eyebrow="Retour d'expérience"
                title="Ce qu'on a appris."
                subtitle="Six insights concrets tirés de la construction d'un système RAG en production."
              />
              <div className="space-y-2">
                {LESSONS.map((l, i) => <LessonCard key={l.title} number={i + 1} {...l} />)}
              </div>

              {/* CTA */}
              <FadeIn delay={0.4} className="mt-20">
                <div className="rounded-[32px] border border-white/[0.06] p-10 text-center relative overflow-hidden"
                  style={{ background: 'rgba(255,255,255,0.015)' }}>
                  <div className="absolute inset-0 pointer-events-none rounded-[32px]"
                    style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(245,158,11,0.05) 0%, transparent 60%)' }} />
                  <Sparkles size={20} className="text-[#F59E0B] mx-auto mb-5" />
                  <h3 className="text-3xl md:text-4xl font-serif-custom tracking-tighter text-white mb-3">
                    Prêt à interroger l'Oracle ?
                  </h3>
                  <p className="text-white/30 text-sm mb-8 max-w-md mx-auto">
                    Le système tourne. Vos documents, vos règles, votre lore — indexés et consultables en temps réel.
                  </p>
                  <a href="/chat"
                    className="inline-flex items-center gap-2 px-8 py-4 rounded-full bg-white text-black font-bold text-sm uppercase tracking-widest hover:scale-105 active:scale-95 transition-all shadow-xl">
                    Lancer une session <ArrowUpRight size={16} />
                  </a>
                </div>
              </FadeIn>
            </section>

          </main>
        </div>
      </div>
    </div>
  );
}
