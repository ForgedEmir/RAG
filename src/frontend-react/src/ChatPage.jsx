import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronLeft, PanelLeftClose, PanelLeftOpen, Plus, MessageSquare,
  Trash2, LogOut, Sparkles, FileText, ChevronDown,
  Check, ArrowUp, Square, Menu, ArrowUpRight,
  ThumbsUp, ThumbsDown, Volume2, VolumeX, Settings
} from 'lucide-react';
import { useChat } from './useChat.js';
import { logout, getSupabase } from './auth.js';
import { useNavigate } from 'react-router-dom';

// ============================================================================
// STYLES GLOBAUX
// ============================================================================
const styles = `
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

.chat-root {
  --bg: #000000;
  --surface: rgba(255,255,255,0.03);
  --border: rgba(255,255,255,0.07);
  --accent: #5ed29c;
  --text: #ffffff;
  background-color: var(--bg);
  color: var(--text);
  font-family: 'Inter', sans-serif;
}

.font-serif-italic { font-family: 'Instrument Serif', serif; font-style: italic; }
.font-mono { font-family: 'JetBrains Mono', monospace; }

.liquid-glass {
  background: rgba(255,255,255,0.015);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.05);
  position: relative;
  overflow: hidden;
}

.liquid-glass::before {
  content:''; position:absolute; inset:0; border-radius:inherit; padding:1px;
  background: linear-gradient(180deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0) 100%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude; pointer-events: none;
}

.hide-scrollbar::-webkit-scrollbar { display: none; }
.hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
`;

// ============================================================================
// MARKDOWN RENDERER (Custom)
// ============================================================================

const CodeBlock = ({ lang, code }) => {
  return (
    <div className="relative bg-white/5 rounded-xl p-4 mt-3 mb-4 group">
      {lang && <div className="absolute top-0 right-0 px-3 py-1 bg-black/40 rounded-bl-xl rounded-tr-xl text-[9px] text-white/30 uppercase tracking-widest">{lang}</div>}
      <pre className="font-mono text-xs text-white/80 overflow-x-auto hide-scrollbar whitespace-pre-wrap leading-relaxed">{code.trim()}</pre>
    </div>
  );
};

const renderInline = (text) => {
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*')) return <em key={i} className="italic text-white/65">{part.slice(1, -1)}</em>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i} className="bg-[#5ed29c]/10 text-[#5ed29c] rounded px-1.5 py-0.5 text-xs font-mono">{part.slice(1, -1)}</code>;
    return <span key={i}>{part}</span>;
  });
};

const renderMarkdown = (content) => {
  if (!content) return null;
  const blocks = [];
  const codeRegex = /```(\w+)?\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;

  while ((match = codeRegex.exec(content)) !== null) {
    if (match.index > lastIndex) blocks.push({ type: 'text', content: content.slice(lastIndex, match.index) });
    blocks.push({ type: 'code', lang: match[1] || '', code: match[2] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) blocks.push({ type: 'text', content: content.slice(lastIndex) });

  return blocks.map((block, idx) => {
    if (block.type === 'code') return <CodeBlock key={idx} lang={block.lang} code={block.code} />;

    return block.content.split('\n\n').map((p, i) => {
      if (!p.trim()) return null;
      if (p.startsWith('### ')) return <h3 key={`${idx}-${i}`} className="font-serif-italic text-[15px] text-white mt-5 mb-2">{renderInline(p.slice(4))}</h3>;
      if (p.startsWith('## ')) return <h2 key={`${idx}-${i}`} className="font-serif-italic text-[17px] text-white mt-5 mb-2">{renderInline(p.slice(3))}</h2>;
      if (p.startsWith('# ')) return <h1 key={`${idx}-${i}`} className="font-serif-italic text-[20px] text-white mt-6 mb-3">{renderInline(p.slice(2))}</h1>;
      if (p.startsWith('- ') || p.startsWith('* ')) {
        const items = p.split('\n').filter(l => l.trim().startsWith('- ') || l.trim().startsWith('* '));
        return (
          <ul key={`${idx}-${i}`} className="space-y-1.5 my-3">
            {items.map((item, j) => (
              <li key={j} className="flex items-start gap-3">
                <span className="text-[#5ed29c] mt-[7px] text-[6px]">●</span>
                <span className="text-[14px] leading-[1.75] text-white/85">{renderInline(item.replace(/^[-*]\s/, ''))}</span>
              </li>
            ))}
          </ul>
        );
      }
      return <p key={`${idx}-${i}`} className="text-[14px] leading-[1.75] text-white/85 mb-4">{renderInline(p)}</p>;
    });
  });
};

// ============================================================================
// COMPOSANTS UI
// ============================================================================

const AmbientBackground = () => (
  <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden bg-black">
    {/* Vidéo de fond */}
    <video
      className="absolute inset-0 w-full h-full object-cover opacity-50 mix-blend-screen"
      src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4"
      muted autoPlay loop playsInline
    />
    {/* Flou glassmorphism par-dessus la vidéo */}
    <div className="absolute inset-0 bg-black/50 backdrop-blur-[60px]" />
    {/* Blobs lumineux */}
    <motion.div
      className="absolute top-0 left-[10%] w-[600px] h-[600px] bg-[#5ed29c] opacity-[0.07] rounded-full blur-[120px]"
      animate={{ x: [0, 60, -30, 0], y: [0, -40, 50, 0] }}
      transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
    />
    <motion.div
      className="absolute bottom-0 right-[10%] w-[500px] h-[500px] bg-[#1a5a3a] opacity-[0.18] rounded-full blur-[140px]"
      animate={{ x: [0, -50, 40, 0], y: [0, 60, -20, 0] }}
      transition={{ duration: 25, repeat: Infinity, ease: "easeInOut" }}
    />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,rgba(0,0,0,0.8)_130%)]" />
  </div>
);

const SidebarItem = ({ session, isActive, onClick, onDelete }) => {
  const [confirm, setConfirm] = useState(false);

  return (
    <div
      onClick={onClick}
      className={`group relative flex items-center gap-2.5 px-3 py-2.5 mx-3 rounded-xl cursor-pointer transition-all ${isActive ? 'bg-white/[0.06] border-l-2 border-l-[#5ed29c]' : 'hover:bg-white/[0.03] border-l-2 border-l-transparent'}`}
    >
      <MessageSquare size={14} className={`shrink-0 ${isActive ? 'text-white' : 'text-white/30'}`} />

      <AnimatePresence mode="wait" initial={false}>
        {confirm ? (
          <motion.div
            key="confirm"
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.92 }}
            transition={{ duration: 0.12 }}
            className="flex-1 flex items-center justify-between gap-2"
            onClick={e => e.stopPropagation()}
          >
            <span className="text-[10px] text-[#f87171]/80 tracking-widest uppercase">Supprimer ?</span>
            <div className="flex items-center gap-1">
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(session.id); }}
                className="w-6 h-6 rounded-lg bg-[#f87171]/10 hover:bg-[#f87171]/20 border border-[#f87171]/20 flex items-center justify-center text-[#f87171] transition-all"
              >
                <Check size={11} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); setConfirm(false); }}
                className="w-6 h-6 rounded-lg bg-white/[0.04] hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/40 hover:text-white transition-all"
              >
                <X size={11} />
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="normal"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1 }}
            className="flex-1 flex items-center justify-between gap-2 overflow-hidden"
          >
            <span className={`text-[12px] truncate ${isActive ? 'text-white font-medium' : 'text-white/60'}`}>{session.title}</span>
            <button
              onClick={(e) => { e.stopPropagation(); setConfirm(true); }}
              className="opacity-0 group-hover:opacity-100 shrink-0 w-6 h-6 rounded-lg flex items-center justify-center text-white/20 hover:text-[#f87171] hover:bg-[#f87171]/10 transition-all"
            >
              <Trash2 size={13} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// X icon needed for confirm dialog
const X = ({ size, className }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

const EmptyState = ({ onSuggest }) => {
  const suggestions = [
    "Qui est le personnage principal ?",
    "Résume l'architecture du système",
    "Quelles sont les factions existantes ?",
    "Décris les lieux importants"
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center h-full max-w-3xl mx-auto px-6 w-full text-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="inline-flex items-center gap-3 liquid-glass px-4 py-2 rounded-full mb-8 border border-white/10 shadow-2xl"
      >
        <div className="bg-[#5ed29c] text-black text-[9px] font-bold px-1.5 py-0.5 rounded uppercase">Nouvelle</div>
        <span className="text-white/40 text-[10px] tracking-[0.3em] uppercase">Session LoreKeeper</span>
      </motion.div>

      <h1 className="font-serif-italic text-6xl md:text-8xl text-white mb-6 tracking-tighter leading-[0.9]">Que cherches-tu ?</h1>
      <p className="text-lg text-white/40 mb-16 font-light italic max-w-lg mx-auto">"Plonge dans les archives. Pose ta question et laisse l'ordre émerger du chaos."</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
        {suggestions.map((text, i) => (
          <motion.button
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + i * 0.1 }}
            onClick={() => onSuggest(text)}
            className="flex items-center gap-4 p-5 rounded-[24px] border border-white/[0.05] liquid-glass hover:bg-[#5ed29c]/5 hover:border-[#5ed29c]/30 hover:shadow-[0_0_30px_rgba(94,210,156,0.05)] transition-all text-left group"
          >
            <div className="p-3 rounded-full bg-white/5 group-hover:bg-[#5ed29c]/10 transition-colors shrink-0">
              <MessageSquare size={16} className="text-white/40 group-hover:text-[#5ed29c] transition-colors" />
            </div>
            <span className="text-[13px] text-white/50 group-hover:text-white/90 transition-colors font-medium tracking-wide">{text}</span>
          </motion.button>
        ))}
      </div>
    </div>
  );
};

// ── Animated placeholder hook ─────────────────────────────────────────────
const PLACEHOLDERS = [
  'Interroger LoreKeeper…',
  'Qui sont les personnages principaux ?',
  'Décris le système de magie runique…',
  'Résume les factions du monde…',
  'Quels artefacts légendaires existent ?',
];

function useAnimatedPlaceholder() {
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const t = setInterval(() => {
      setVisible(false);
      setTimeout(() => { setIndex(i => (i + 1) % PLACEHOLDERS.length); setVisible(true); }, 340);
    }, 3400);
    return () => clearInterval(t);
  }, []);
  return { text: PLACEHOLDERS[index], visible };
}

// ── TTS hook ────────────────────────────────────────────────────────────────
function useTTS() {
  const [speaking, setSpeaking] = useState(false);
  const uttRef = useRef(null);

  const speak = (text) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = 'fr-FR';
    utt.rate = 0.88;
    utt.pitch = 0.72; // voix grave pour l'Oracle

    const applyVoiceAndSpeak = () => {
      const voices = window.speechSynthesis.getVoices();
      // Cherche une voix masculine française (Thomas, Henri, Claude, Pierre…)
      const maleVoice = voices.find(v =>
        v.lang.startsWith('fr') &&
        /thomas|henri|claude|pierre|paul|antoine|nicolas/i.test(v.name)
      ) || voices.find(v =>
        v.lang.startsWith('fr') &&
        !/marie|pauline|amélie|amel|lea|lucie|celine|valerie/i.test(v.name)
      ) || voices.find(v => v.lang.startsWith('fr'));
      if (maleVoice) utt.voice = maleVoice;
      utt.onstart = () => setSpeaking(true);
      utt.onend = () => setSpeaking(false);
      utt.onerror = () => setSpeaking(false);
      uttRef.current = utt;
      window.speechSynthesis.speak(utt);
    };

    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      applyVoiceAndSpeak();
    } else {
      // Les voix se chargent de façon asynchrone au premier appel
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null;
        applyVoiceAndSpeak();
      };
    }
  };

  const stop = () => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  };

  return { speak, stop, speaking };
}

const MessageBubble = ({ msg, sessionId }) => {
  const [vote, setVote] = useState(null);
  const { speak, stop, speaking } = useTTS();
  const [ttsActive, setTtsActive] = useState(false);
  const [expandedSources, setExpandedSources] = useState({});

  // Reconstruction robuste des passages par source
  const chunksBySource = useMemo(() => {
    const acc = {};
    const rawChunks = msg.context_chunks || [];
    const rawPassages = msg.passages || [];
    const rawSources = msg.sources || [];

    if (rawChunks.length > 0 && typeof rawChunks[0] === 'object') {
      // Format moderne : [{source, passage}, ...]
      rawChunks.forEach(c => {
        const s = c.source || 'Archive';
        if (!acc[s]) acc[s] = [];
        if (c.passage) acc[s].push(c.passage);
      });
    } else if (rawPassages.length > 0) {
      // Format de secours ou ancien format : passages et sources séparés
      rawPassages.forEach((p, i) => {
        const s = rawSources[i] || rawSources[0] || 'Archive';
        if (!acc[s]) acc[s] = [];
        acc[s].push(p);
      });
    }
    return acc;
  }, [msg.context_chunks, msg.passages, msg.sources]);

  const displaySources = useMemo(() => {
    const fromMsg = msg.sources || [];
    const fromChunks = Object.keys(chunksBySource);
    return Array.from(new Set([...fromMsg, ...fromChunks]));
  }, [msg.sources, chunksBySource]);

  const toggleSource = (src) => {
    setExpandedSources(prev => ({ ...prev, [src]: !prev[src] }));
  };

  const handleVote = async (direction) => {
    const newVote = vote === direction ? null : direction;
    setVote(newVote);
    if (!newVote || !sessionId) return;

    // pouce haut = 5 (bon) ; pouce bas = 1 (mauvais)
    const rating = newVote === 'up' ? 5 : 1;
    const voteValue = newVote === 'up' ? 1 : -1;
    try {
      const headers = { 'Content-Type': 'application/json' };
      try {
        const sb = await getSupabase();
        if (sb) {
          const { data } = await sb.auth.getSession();
          const token = data?.session?.access_token;
          if (token) headers['Authorization'] = `Bearer ${token}`;
        }
      } catch (_) {}

      const traceId = msg.trace_id || '';
      if (traceId) {
        const voteResp = await fetch('/api/feedback/vote', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            trace_id: traceId,
            value: voteValue,
            session_id: sessionId,
            question: msg.question_for_feedback || '',
            answer: msg.answer_for_feedback || msg.content || '',
          }),
        });

        if (voteResp.ok) return;
      }

      await fetch('/api/feedback', {
        method: 'POST',
        headers,
        body: JSON.stringify({ session_id: sessionId, rating }),
      });
    } catch (_) {}
  };

  const handleTTS = () => {
    if (ttsActive) {
      stop();
      setTtsActive(false);
    } else {
      // Strip markdown pour la lecture
      const plain = msg.content
        .replace(/```[\s\S]*?```/g, 'bloc de code.')
        .replace(/[#*`_~]/g, '')
        .replace(/\n{2,}/g, '. ')
        .replace(/\n/g, ' ')
        .trim();
      speak(plain);
      setTtsActive(true);
    }
  };

  // Sync ttsActive avec l'état réel de la synthèse
  useEffect(() => {
    if (!speaking) setTtsActive(false);
  }, [speaking]);

  useEffect(() => {
    setExpandedSources({});
  }, [msg.id]);

  if (msg.role === 'user') {
    return (
      <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} className="flex justify-end w-full">
        <div className="max-w-[85%] md:max-w-[72%] liquid-glass bg-white/[0.04] border border-white/[0.08] rounded-[32px] rounded-tr-[8px] px-7 py-5 shadow-2xl">
          <p className="text-[15px] leading-[1.6] text-white/90 whitespace-pre-wrap font-light">{msg.content}</p>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} className="flex gap-4 w-full group relative">
      <div className="relative shrink-0 w-[28px] h-[28px] mt-1 flex items-center justify-center bg-[#5ed29c]/10 border border-[#5ed29c]/20 rounded-full">
        <Sparkles size={13} className="text-[#5ed29c]" />
        {msg.streaming && (
          <motion.div
            className="absolute inset-0 rounded-full border border-[#5ed29c]"
            animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center mb-2">
          <span className="text-[10px] uppercase tracking-widest text-white/25">LoreKeeper</span>
        </div>

        {msg.streaming && !msg.content ? (
          <div className="flex gap-1.5 items-center h-6 mt-2">
            {[0, 1, 2].map(i => (
              <motion.div key={i} className="w-1.5 h-1.5 bg-white/25 rounded-full" animate={{ y: [0, -6, 0], opacity: [0.25, 1, 0.25] }} transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }} />
            ))}
          </div>
        ) : (
          <div className="prose-custom max-w-none">
            {renderMarkdown(msg.content)}
            {msg.streaming && <motion.span animate={{ opacity: [1, 0, 1] }} transition={{ duration: 0.8, repeat: Infinity }} className="inline-block w-[2px] h-[14px] bg-[#5ed29c] ml-1 align-middle" />}
          </div>
        )}

        {/* Actions : TTS, Like, Dislike — toujours visibles après la réponse */}
        {!msg.streaming && msg.content && (
          <div className="flex items-center gap-1.5 mt-4">
            <button
              onClick={handleTTS}
              title={ttsActive ? 'Arrêter' : 'Écouter'}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] border transition-all ${
                ttsActive
                  ? 'border-[#5ed29c]/40 text-[#5ed29c] bg-[#5ed29c]/10'
                  : 'border-white/[0.06] text-white/30 hover:text-white/70 hover:border-white/20 hover:bg-white/[0.04]'
              }`}
            >
              {ttsActive ? <VolumeX size={11} /> : <Volume2 size={11} />}
              <span>{ttsActive ? 'Stop' : 'Écouter'}</span>
            </button>
            <button
              onClick={() => handleVote('up')}
              title="Utile"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] border transition-all ${
                vote === 'up'
                  ? 'border-[#5ed29c]/40 text-[#5ed29c] bg-[#5ed29c]/10'
                  : 'border-white/[0.06] text-white/30 hover:text-white/70 hover:border-white/20 hover:bg-white/[0.04]'
              }`}
            >
              <ThumbsUp size={11} />
              <span>Utile</span>
            </button>
            <button
              onClick={() => handleVote('down')}
              title="Pas utile"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] border transition-all ${
                vote === 'down'
                  ? 'border-[#f87171]/40 text-[#f87171] bg-[#f87171]/10'
                  : 'border-white/[0.06] text-white/30 hover:text-white/70 hover:border-white/20 hover:bg-white/[0.04]'
              }`}
            >
              <ThumbsDown size={11} />
              <span>Pas utile</span>
            </button>
          </div>
        )}

        <AnimatePresence>
          {!msg.streaming && displaySources.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="mt-6 pt-4 border-t border-white/[0.04]">
              <div className="text-[9px] uppercase tracking-widest text-white/20 mb-2">Sources analysées (cliquer pour afficher les passages)</div>
              <div className="flex flex-wrap gap-2 items-center">
                {displaySources.map((src, i) => {
                  const chunks = chunksBySource[src] || [];
                  const hasChunks = chunks.length > 0;
                  const isOpen = !!expandedSources[src];
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={() => toggleSource(src, hasChunks)}
                      className={`flex items-center gap-1.5 rounded-full px-3 py-1 border transition-colors text-[10px] ${
                        hasChunks
                          ? 'bg-white/[0.04] border-white/[0.08] hover:border-[#5ed29c]/30 text-white/45 hover:text-white/80 cursor-pointer'
                          : 'bg-white/[0.02] border-white/[0.06] text-white/30 cursor-default'
                      }`}
                    >
                      <FileText size={10} />
                      <span>{src}</span>
                      {hasChunks && (
                        <>
                          <span className="text-white/20">·</span>
                          <span className="text-[#5ed29c]/85">{chunks.length}</span>
                          <ChevronDown size={11} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                        </>
                      )}
                    </button>
                  );
                })}

              </div>

              <div className="mt-3 space-y-2">
                <AnimatePresence initial={false}>
                  {displaySources.map((src) => {
                    const chunks = chunksBySource[src] || [];
                    const isOpen = !!expandedSources[src];
                    if (!isOpen || chunks.length === 0) return null;
                    return (
                      <motion.div
                        key={src}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        className="rounded-2xl border border-white/[0.08] bg-white/[0.02] px-4 py-3"
                      >
                        <div className="text-[10px] text-[#5ed29c]/90 mb-2">{src}</div>
                        <div className="space-y-2">
                          {chunks.map((passage, idx) => (
                            <p key={`${src}-${idx}`} className="text-[12px] leading-[1.65] text-white/70 whitespace-pre-wrap">
                              {passage}
                            </p>
                          ))}
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

// ============================================================================
// PAGE PRINCIPALE
// ============================================================================

export default function ChatPage({ user, onLogout, initialQuestion }) {
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 768);
  const { sessions, activeSession, activeId, streaming, newSession, selectSession, deleteSession, send, abort } = useChat();

  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const initTriggered = useRef(false);
  const { text: animatedPlaceholder, visible: placeholderVisible } = useAnimatedPlaceholder();


  useEffect(() => {
    if (initialQuestion && !initTriggered.current) {
      initTriggered.current = true;
      send(initialQuestion);
    }
  }, [initialQuestion, send]);

  const handleInput = (e) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  };

  const handleSubmit = () => {
    const q = input.trim();
    if (!q || streaming) return;
    send(q, activeId || undefined);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setAutoScroll(true);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === 'Escape' && streaming) abort();
  };

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 100);
  };

  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeSession?.messages, autoScroll]);

  const today = sessions.slice(0, 1);
  const older = sessions.slice(1);

  const handleLogout = async () => {
    await logout();
    if (onLogout) onLogout();
    navigate('/');
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="chat-root h-screen w-full flex overflow-hidden relative">
      <style dangerouslySetInnerHTML={{ __html: styles }} />
      <AmbientBackground />

      <AnimatePresence>
        {sidebarOpen && window.innerWidth < 768 && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
          />
        )}
      </AnimatePresence>

      {/* SIDEBAR */}
      <motion.aside
        initial={false}
        animate={{ width: sidebarOpen ? 260 : 0, opacity: sidebarOpen ? 1 : 0 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="liquid-glass border-r border-white/[0.06] flex flex-col z-50 h-full fixed md:relative shrink-0 overflow-hidden"
      >
        <div className="w-[260px] flex flex-col h-full">
          <div className="h-[52px] flex items-center justify-between px-4 border-b border-white/[0.05] shrink-0">
            <div className="flex items-center gap-3">
              <button onClick={() => navigate('/')} className="text-white/40 hover:text-white transition-colors"><ChevronLeft size={18} /></button>
              <span className="font-serif-italic text-[18px]">LoreKeeper</span>
            </div>
            <button onClick={() => setSidebarOpen(false)} className="text-white/40 hover:text-white transition-colors"><PanelLeftClose size={18} /></button>
          </div>

          <div className="p-4 shrink-0">
            <button
              onClick={() => { newSession(); if(window.innerWidth<768) setSidebarOpen(false); }}
              className="w-full flex items-center gap-2 justify-center py-2.5 border border-dashed border-white/10 rounded-xl text-[13px] text-white/70 hover:border-[#5ed29c]/30 hover:bg-[#5ed29c]/5 hover:text-white transition-all group"
            >
              <Plus size={16} className="text-white/40 group-hover:text-[#5ed29c]" /> Nouvelle conversation
            </button>
          </div>

          <div className="flex-1 overflow-y-auto hide-scrollbar pb-4 flex flex-col gap-4">
            {today.length > 0 && (
              <div>
                <div className="px-5 mb-2 text-[9px] uppercase tracking-widest text-white/20">Aujourd'hui</div>
                <div className="flex flex-col gap-1">
                  {today.map(s => <SidebarItem key={s.id} session={s} isActive={s.id === activeId} onClick={() => { selectSession(s.id); if(window.innerWidth<768) setSidebarOpen(false); }} onDelete={deleteSession} />)}
                </div>
              </div>
            )}
            {older.length > 0 && (
              <div>
                <div className="px-5 mb-2 text-[9px] uppercase tracking-widest text-white/20">Historique</div>
                <div className="flex flex-col gap-1">
                  {older.map(s => <SidebarItem key={s.id} session={s} isActive={s.id === activeId} onClick={() => { selectSession(s.id); if(window.innerWidth<768) setSidebarOpen(false); }} onDelete={deleteSession} />)}
                </div>
              </div>
            )}
          </div>

          <div className="p-4 border-t border-white/[0.05] shrink-0 group relative cursor-pointer hover:bg-white/[0.02] transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-[28px] h-[28px] rounded-full bg-white/10 flex items-center justify-center text-xs border border-white/5">
                {user?.isGuest ? '👤' : (user?.email?.charAt(0).toUpperCase() || '?')}
              </div>
              <div className="flex-1 overflow-hidden">
                <div className="text-[12px] truncate text-white/80">{user?.isGuest ? 'Mode Invité' : (user?.email || 'Connecté')}</div>
              </div>
              <button onClick={handleLogout} className="opacity-0 group-hover:opacity-100 text-white/40 hover:text-[#f87171] transition-all p-1"><LogOut size={14} /></button>
            </div>
          </div>
        </div>
      </motion.aside>

      {/* MAIN CHAT AREA */}
      <main className="flex-1 flex flex-col relative min-w-0 z-10">

        <header className="h-[52px] border-b border-white/[0.05] flex items-center justify-between px-4 shrink-0 bg-transparent relative z-20">
          <div className="flex items-center gap-3 overflow-hidden">
            {!sidebarOpen && <button onClick={() => setSidebarOpen(true)} className="text-white/40 hover:text-white transition-colors p-1"><PanelLeftOpen size={18} /></button>}
            <span className="text-[13px] text-white/70 truncate">{activeSession?.title || 'Nouvelle conversation'}</span>
          </div>

          <div className="flex items-center gap-2">
            <AnimatePresence>
              {streaming && (
                <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="flex items-center gap-2 mr-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#5ed29c] animate-pulse" />
                  <span className="text-[10px] text-[#5ed29c] uppercase tracking-widest hidden md:block">En train de répondre…</span>
                </motion.div>
              )}
            </AnimatePresence>
            {activeSession && (
              <button onClick={() => deleteSession(activeSession.id)} className="text-white/20 hover:text-white/50 transition-colors p-1.5 rounded-lg hover:bg-white/[0.04]" title="Effacer la conversation"><Trash2 size={15} /></button>
            )}
            <button
              onClick={() => window.open('/monitoring', '_blank')}
              title="Panel Monitoring"
              className="text-white/20 hover:text-white/60 transition-colors p-1.5 rounded-lg hover:bg-white/[0.04]"
            >
              <Settings size={15} />
            </button>
          </div>
        </header>

        <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto hide-scrollbar px-4 md:px-8 py-6">
          <div className="max-w-[760px] mx-auto flex flex-col gap-8 pb-10">
            {!activeSession?.messages?.length ? (
              <EmptyState onSuggest={(text) => { send(text, activeId || undefined); setAutoScroll(true); }} />
            ) : (
              activeSession.messages.map(msg => <MessageBubble key={msg.id} msg={msg} sessionId={activeId} />)
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="w-full px-4 md:px-8 py-6 shrink-0 relative z-20">
          <div className="max-w-[760px] mx-auto">

            {/* Action chips — follow-up suggestions when conversation active */}
            <AnimatePresence>
              {!streaming && activeSession?.messages?.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-center gap-2 mb-3 flex-wrap"
                >
                  {['Développe ce point', 'Donne des exemples', 'Simplifie', 'Quels personnages ?'].map((chip, i) => (
                    <motion.button
                      key={chip}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: i * 0.04 }}
                      whileHover={{ y: -1 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => { send(chip, activeId || undefined); setAutoScroll(true); }}
                      className="px-3.5 py-1.5 rounded-full text-[11px] transition-all duration-150"
                      style={{ border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)', color: 'rgba(255,255,255,0.35)' }}
                      onMouseEnter={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.7)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.14)'; }}
                      onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.35)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; }}
                    >
                      {chip}
                    </motion.button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Input — animated border glow when streaming */}
            <div
              className="liquid-glass rounded-[48px] p-2 shadow-2xl flex items-end gap-2 transition-all duration-300"
              style={{
                background: streaming ? 'rgba(0,0,0,0.75)' : 'rgba(0,0,0,0.6)',
                border: streaming ? '1px solid rgba(94,210,156,0.32)' : '1px solid rgba(255,255,255,0.1)',
                boxShadow: streaming ? '0 0 0 3px rgba(94,210,156,0.07), 0 20px 60px rgba(0,0,0,0.5)' : '0 20px 60px rgba(0,0,0,0.4)',
              }}
            >
              <div className="flex-1 flex items-center min-h-[56px] pl-6 pr-2">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInput}
                  onKeyDown={handleKeyDown}
                  placeholder={animatedPlaceholder}
                  className="w-full bg-transparent border-none outline-none text-white/90 text-[16px] leading-[1.5] resize-none hide-scrollbar font-light self-center"
                  style={{
                    caretColor: '#5ed29c',
                    opacity: !placeholderVisible && !input ? 0.85 : 1,
                    transition: 'opacity 0.3s',
                    paddingTop: 0,
                    paddingBottom: 0,
                    margin: 0,
                  }}
                  rows={1}
                />
              </div>

              <div className="shrink-0 flex items-center gap-1 p-2">

                {streaming ? (
                  <motion.button
                    onClick={abort}
                    whileHover={{ scale: 1.06 }}
                    whileTap={{ scale: 0.92 }}
                    className="flex items-center justify-center w-12 h-12 rounded-full transition-colors"
                    style={{ background: 'rgba(94,210,156,0.1)', border: '1px solid rgba(94,210,156,0.25)', color: '#5ed29c' }}
                  >
                    <Square size={14} fill="currentColor" />
                  </motion.button>
                ) : (
                  <motion.button
                    onClick={handleSubmit}
                    disabled={!input.trim()}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.93 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                    className="flex items-center justify-center w-12 h-12 rounded-full bg-white text-black disabled:opacity-30 disabled:cursor-not-allowed shadow-lg"
                  >
                    <ArrowUpRight size={22} strokeWidth={2} />
                  </motion.button>
                )}
              </div>
            </div>

            <div className="flex justify-center items-center px-6 mt-3">
              <div className="text-[10px] text-white/20 uppercase tracking-widest flex items-center gap-1.5">
                <Sparkles size={10} className="text-[#5ed29c]/50" /> Propulsé par LoreKeeper RAG
              </div>
            </div>
          </div>
        </div>

      </main>
    </motion.div>
  );
}
