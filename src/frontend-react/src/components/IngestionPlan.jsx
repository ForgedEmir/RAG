import React, { useState } from 'react';
import { CheckCircle2, Circle, CircleAlert, CircleDotDashed, CircleX } from 'lucide-react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';

// ── Données pipeline RAG LoreKeeper ──────────────────────────────────────────
const PIPELINE_TASKS = [
  {
    id: '1',
    title: 'Réception des fichiers',
    description: 'Validation et réception des documents déposés via drag & drop ou upload.',
    status: 'completed',
    level: 0,
    dependencies: [],
    subtasks: [
      {
        id: '1.1',
        title: 'Validation extension & taille',
        description: 'Vérifie que le fichier est dans les formats supportés (PDF, DOCX, MD, CSV, JSON, TXT) et ne dépasse pas 500 Ko.',
        status: 'completed',
        tools: ['validator', 'file-system'],
      },
      {
        id: '1.2',
        title: 'Détection MIME & encodage',
        description: 'Détecte le type MIME réel du fichier et l\'encodage (UTF-8, latin-1…) pour éviter les erreurs de lecture.',
        status: 'completed',
        tools: ['parser', 'charset-detector'],
      },
      {
        id: '1.3',
        title: 'Rejet des doublons',
        description: 'Compare le hash SHA-256 du fichier avec les documents existants. Rejette silencieusement si déjà indexé.',
        status: 'completed',
        tools: ['qdrant', 'hash-checker'],
      },
    ],
  },
  {
    id: '2',
    title: 'Parsing du document',
    description: 'Extraction et nettoyage du texte brut depuis le format source.',
    status: 'completed',
    level: 0,
    dependencies: [],
    subtasks: [
      {
        id: '2.1',
        title: 'Extraction texte (PDF / DOCX / MD)',
        description: 'Utilise pdfminer pour PDF, python-docx pour DOCX, markdown pour MD. Préserve la structure des paragraphes.',
        status: 'completed',
        tools: ['pdfminer', 'python-docx', 'markdown-parser'],
      },
      {
        id: '2.2',
        title: 'Nettoyage & normalisation Unicode',
        description: 'Supprime les caractères de contrôle, normalise les espaces, corrige les ligatures typographiques (ﬁ → fi).',
        status: 'completed',
        tools: ['unicode-normalizer', 'text-cleaner'],
      },
      {
        id: '2.3',
        title: 'Extraction métadonnées',
        description: 'Récupère titre, auteur, date si disponibles (PDF metadata, YAML front-matter MD). Stocké dans Qdrant payload.',
        status: 'completed',
        tools: ['metadata-extractor', 'qdrant'],
      },
    ],
  },
  {
    id: '3',
    title: 'Chunking contextuel',
    description: 'Découpage hiérarchique en chunks parent (contexte large) et enfants (granularité fine).',
    status: 'in-progress',
    level: 0,
    dependencies: [],
    subtasks: [
      {
        id: '3.1',
        title: 'Chunks parents (contexte)',
        description: 'Segments de ~1500 tokens avec overlap de 200. Servent de contexte lors de la génération de la réponse.',
        status: 'completed',
        tools: ['chunker', 'token-counter'],
      },
      {
        id: '3.2',
        title: 'Chunks enfants (recherche)',
        description: 'Sous-segments de ~400 tokens issus des chunks parents. Ce sont eux qui sont indexés dans Qdrant et BM25.',
        status: 'in-progress',
        tools: ['chunker', 'token-counter'],
      },
      {
        id: '3.3',
        title: 'Liaison parent↔enfant',
        description: 'Chaque chunk enfant stocke l\'id du chunk parent dans ses métadonnées pour permettre le context retrieval.',
        status: 'pending',
        tools: ['chunker', 'qdrant'],
      },
    ],
  },
  {
    id: '4',
    title: 'Embedding vectoriel',
    description: 'Génération des vecteurs de représentation sémantique via FastEmbed (ONNX, zéro GPU requis).',
    status: 'pending',
    level: 1,
    dependencies: ['3'],
    subtasks: [
      {
        id: '4.1',
        title: 'Chargement modèle FastEmbed',
        description: 'Charge BAAI/bge-small-en-v1.5 (384 dim) en mémoire. Singleton — chargé une seule fois au warmup.',
        status: 'pending',
        tools: ['fastembed', 'onnx-runtime'],
      },
      {
        id: '4.2',
        title: 'Génération embeddings par batch',
        description: 'Traite les chunks par lots de 32 pour optimiser le débit. Normalisation L2 automatique.',
        status: 'pending',
        tools: ['fastembed', 'numpy'],
      },
      {
        id: '4.3',
        title: 'Validation dimension',
        description: 'Vérifie que la dimension des vecteurs (384) correspond à la collection Qdrant. Recréation si mismatch.',
        status: 'pending',
        tools: ['qdrant', 'validator'],
      },
    ],
  },
  {
    id: '5',
    title: 'Indexation Qdrant',
    description: 'Upsert des vecteurs et métadonnées dans la base vectorielle Qdrant.',
    status: 'pending',
    level: 1,
    dependencies: ['4'],
    subtasks: [
      {
        id: '5.1',
        title: 'Upsert vecteurs & payload',
        description: 'Insère ou met à jour les chunks dans la collection. Le payload contient texte, fichier, chunk_type, parent_id.',
        status: 'pending',
        tools: ['qdrant-client', 'file-system'],
      },
      {
        id: '5.2',
        title: 'Gestion collection & index HNSW',
        description: 'Crée la collection si inexistante avec les paramètres HNSW optimisés (m=16, ef=100). Distance cosine.',
        status: 'pending',
        tools: ['qdrant-client'],
      },
    ],
  },
  {
    id: '6',
    title: 'Mise à jour BM25',
    description: 'Reconstruction du corpus BM25 pour la recherche lexicale exacte (complémentaire au vectoriel).',
    status: 'pending',
    level: 1,
    dependencies: ['3'],
    subtasks: [
      {
        id: '6.1',
        title: 'Tokenisation FR (stopwords)',
        description: 'Tokenise le texte en retirant les stopwords français (de, le, la…) et en normalisant les accents.',
        status: 'pending',
        tools: ['bm25-tokenizer', 'unicode-normalizer'],
      },
      {
        id: '6.2',
        title: 'Sauvegarde corpus JSON',
        description: 'Écrit le corpus complet dans bm25_corpus.json (qdrant_db/). Lecture lazy au prochain démarrage.',
        status: 'pending',
        tools: ['file-system'],
      },
      {
        id: '6.3',
        title: 'Rebuild index BM25Okapi',
        description: 'Reconstruit l\'index BM25Okapi en mémoire et invalide le cache pour forcer le rechargement.',
        status: 'pending',
        tools: ['rank-bm25'],
      },
    ],
  },
];

// ── Icône de statut ───────────────────────────────────────────────────────────
const StatusIcon = ({ status, size = 'md' }) => {
  const cls = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';
  const icons = {
    completed:   <CheckCircle2   className={`${cls} text-[#5ed29c]`} />,
    'in-progress': <CircleDotDashed className={`${cls} text-[#60a5fa]`} />,
    'need-help': <CircleAlert    className={`${cls} text-[#fb923c]`} />,
    failed:      <CircleX        className={`${cls} text-[#f87171]`} />,
    pending:     <Circle         className={`${cls} text-white/20`} />,
  };
  return (
    <AnimatePresence mode="wait">
      <motion.div key={status}
        initial={{ opacity: 0, scale: 0.7, rotate: -15 }}
        animate={{ opacity: 1, scale: 1, rotate: 0 }}
        exit={{ opacity: 0, scale: 0.7, rotate: 15 }}
        transition={{ duration: 0.18, ease: [0.2, 0.65, 0.3, 0.9] }}
      >
        {icons[status] ?? icons.pending}
      </motion.div>
    </AnimatePresence>
  );
};

// ── Badge de statut ───────────────────────────────────────────────────────────
const StatusBadge = ({ status }) => {
  const styles = {
    completed:     'bg-[#5ed29c]/10 text-[#5ed29c]',
    'in-progress': 'bg-[#60a5fa]/10 text-[#60a5fa]',
    'need-help':   'bg-[#fb923c]/10 text-[#fb923c]',
    failed:        'bg-[#f87171]/10 text-[#f87171]',
    pending:       'bg-white/5 text-white/25',
  };
  const labels = {
    completed: 'Terminé', 'in-progress': 'En cours',
    'need-help': 'Bloqué', failed: 'Échec', pending: 'En attente',
  };
  return (
    <motion.span key={status}
      className={`rounded px-1.5 py-0.5 text-[10px] font-medium tracking-wide ${styles[status] ?? styles.pending}`}
      initial={{ scale: 1 }} animate={{ scale: [1, 1.07, 1] }}
      transition={{ duration: 0.3 }}
    >
      {labels[status] ?? status}
    </motion.span>
  );
};

// ── Composant principal ───────────────────────────────────────────────────────
export default function IngestionPlan({ liveSteps = null }) {
  // liveSteps: optionnel, reçu du backend pour mettre à jour les statuts en live
  const [tasks, setTasks] = useState(() => {
    if (!liveSteps) return PIPELINE_TASKS;
    return PIPELINE_TASKS.map(t => ({
      ...t,
      status: liveSteps[t.id] ?? t.status,
    }));
  });

  const [expandedTasks, setExpandedTasks] = useState(['1', '2', '3']);
  const [expandedSubtasks, setExpandedSubtasks] = useState({});

  const toggleTask = (id) =>
    setExpandedTasks(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const toggleSubtask = (tid, sid) => {
    const key = `${tid}-${sid}`;
    setExpandedSubtasks(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const cycleStatus = (taskId) => {
    const order = ['pending', 'in-progress', 'completed', 'need-help', 'failed'];
    setTasks(prev => prev.map(t => {
      if (t.id !== taskId) return t;
      const next = order[(order.indexOf(t.status) + 1) % order.length];
      return { ...t, status: next };
    }));
  };

  const cycleSubStatus = (taskId, subtaskId) => {
    setTasks(prev => prev.map(t => {
      if (t.id !== taskId) return t;
      const updatedSubs = t.subtasks.map(s => {
        if (s.id !== subtaskId) return s;
        return { ...s, status: s.status === 'completed' ? 'pending' : 'completed' };
      });
      const allDone = updatedSubs.every(s => s.status === 'completed');
      return { ...t, subtasks: updatedSubs, status: allDone ? 'completed' : t.status };
    }));
  };

  const subtaskListVariants = {
    hidden: { opacity: 0, height: 0, overflow: 'hidden' },
    visible: {
      height: 'auto', opacity: 1, overflow: 'visible',
      transition: { duration: 0.22, staggerChildren: 0.04, when: 'beforeChildren', ease: [0.2, 0.65, 0.3, 0.9] },
    },
    exit: { height: 0, opacity: 0, overflow: 'hidden', transition: { duration: 0.18 } },
  };

  const subtaskVariants = {
    hidden: { opacity: 0, x: -8 },
    visible: { opacity: 1, x: 0, transition: { type: 'spring', stiffness: 500, damping: 28 } },
    exit: { opacity: 0, x: -8, transition: { duration: 0.12 } },
  };

  const detailVariants = {
    hidden: { opacity: 0, height: 0, overflow: 'hidden' },
    visible: { opacity: 1, height: 'auto', overflow: 'visible', transition: { duration: 0.22, ease: [0.2, 0.65, 0.3, 0.9] } },
    exit: { opacity: 0, height: 0, overflow: 'hidden', transition: { duration: 0.15 } },
  };

  return (
    <div className="h-full overflow-auto custom-scrollbar">
      <LayoutGroup>
        <div className="space-y-1">
          {tasks.map((task, index) => {
            const isExpanded = expandedTasks.includes(task.id);

            return (
              <motion.div key={task.id}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05, type: 'spring', stiffness: 400, damping: 30 }}
                className="rounded-xl overflow-hidden"
                style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                {/* ── Ligne tâche ─────────────────────────────── */}
                <motion.div
                  className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
                  whileHover={{ backgroundColor: 'rgba(255,255,255,0.02)' }}
                  onClick={() => toggleTask(task.id)}
                >
                  {/* Icône statut — cliquable séparément */}
                  <div onClick={e => { e.stopPropagation(); cycleStatus(task.id); }}
                    className="flex-shrink-0 hover:scale-110 transition-transform">
                    <StatusIcon status={task.status} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <span className={`text-sm font-medium ${task.status === 'completed' ? 'text-white/30 line-through' : 'text-white/80'}`}>
                      {task.id}. {task.title}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {task.dependencies.length > 0 && (
                      <div className="flex gap-1">
                        {task.dependencies.map(dep => (
                          <span key={dep} className="px-1.5 py-0.5 rounded text-[9px] font-mono text-white/30 bg-white/5">
                            ←{dep}
                          </span>
                        ))}
                      </div>
                    )}
                    <StatusBadge status={task.status} />
                    <motion.span
                      className="text-white/20 text-xs ml-1"
                      animate={{ rotate: isExpanded ? 90 : 0 }}
                      transition={{ duration: 0.18 }}
                    >▶</motion.span>
                  </div>
                </motion.div>

                {/* ── Sous-tâches ──────────────────────────────── */}
                <AnimatePresence mode="wait">
                  {isExpanded && task.subtasks.length > 0 && (
                    <motion.div
                      variants={subtaskListVariants}
                      initial="hidden" animate="visible" exit="exit"
                      layout
                    >
                      {/* Ligne de connexion verticale */}
                      <div className="relative">
                        <div className="absolute top-0 bottom-0 left-[28px] w-px"
                          style={{ background: 'linear-gradient(to bottom, rgba(94,210,156,0.15), transparent)' }} />

                        <ul className="px-3 pb-3 space-y-0.5">
                          {task.subtasks.map(subtask => {
                            const key = `${task.id}-${subtask.id}`;
                            const isSubExpanded = expandedSubtasks[key];

                            return (
                              <motion.li key={subtask.id}
                                variants={subtaskVariants}
                                layout
                                className="pl-6"
                              >
                                <motion.div
                                  className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg cursor-pointer"
                                  whileHover={{ backgroundColor: 'rgba(255,255,255,0.03)' }}
                                  onClick={() => toggleSubtask(task.id, subtask.id)}
                                >
                                  <div onClick={e => { e.stopPropagation(); cycleSubStatus(task.id, subtask.id); }}
                                    className="flex-shrink-0 hover:scale-110 transition-transform">
                                    <StatusIcon status={subtask.status} size="sm" />
                                  </div>
                                  <span className={`text-xs flex-1 ${subtask.status === 'completed' ? 'text-white/25 line-through' : 'text-white/55'}`}>
                                    {subtask.title}
                                  </span>
                                  {subtask.tools && (
                                    <span className="text-[9px] text-white/15 font-mono">
                                      {subtask.tools.length} outil{subtask.tools.length > 1 ? 's' : ''}
                                    </span>
                                  )}
                                </motion.div>

                                {/* Détail sous-tâche */}
                                <AnimatePresence mode="wait">
                                  {isSubExpanded && (
                                    <motion.div
                                      variants={detailVariants}
                                      initial="hidden" animate="visible" exit="exit"
                                      layout
                                      className="ml-7 mt-1 mb-1.5 pl-3 border-l border-dashed border-white/10"
                                    >
                                      <p className="text-[11px] text-white/35 leading-relaxed py-1">
                                        {subtask.description}
                                      </p>
                                      {subtask.tools && subtask.tools.length > 0 && (
                                        <div className="flex flex-wrap gap-1 mt-1 mb-0.5">
                                          {subtask.tools.map((tool, i) => (
                                            <motion.span key={i}
                                              initial={{ opacity: 0, y: -3 }}
                                              animate={{ opacity: 1, y: 0, transition: { delay: i * 0.04 } }}
                                              whileHover={{ y: -1 }}
                                              className="px-1.5 py-0.5 rounded text-[9px] font-mono text-[#5ed29c]/60 bg-[#5ed29c]/5 border border-[#5ed29c]/10"
                                            >
                                              {tool}
                                            </motion.span>
                                          ))}
                                        </div>
                                      )}
                                    </motion.div>
                                  )}
                                </AnimatePresence>
                              </motion.li>
                            );
                          })}
                        </ul>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      </LayoutGroup>
    </div>
  );
}
