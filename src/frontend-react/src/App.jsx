import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Routes, Route, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence, useScroll, useTransform, useMotionValue, useSpring, useInView } from 'framer-motion';
import { ArrowUpRight, Sparkles, X, Check, LogOut, Settings, Database, Search, Brain, Zap, GitBranch, Shield, BarChart3, Layers } from 'lucide-react';
import {
  loginWithEmail, signupWithEmail, loginWithGithub, loginWithGoogle,
  logout, getSession, onAuthStateChange, getOrCreateGuestId,
} from './auth.js';
import ChatPage from './ChatPage.jsx';
import MonitoringRoute from './MonitoringPage.jsx';

// Brand icons not available in lucide-react
const LinkedinIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/>
  </svg>
);

const GithubIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/>
  </svg>
);

const GoogleIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

// --- Styles Globaux ---
const styles = `
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@700&family=Fustat:wght@500;700&family=Schibsted+Grotesk:wght@500;600&display=swap');

:root {
  --font-display: 'Instrument Serif', serif;
  --font-body: 'Inter', sans-serif;
  --background: #000000;
  --foreground: #FFFFFF;
  --primary: #5ed29c;
}

html { scroll-behavior: smooth; }

body {
  background-color: var(--background);
  color: var(--foreground);
  margin: 0;
  font-family: var(--font-body);
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}

.font-serif-custom { font-family: var(--font-display); }

.liquid-glass {
  background: rgba(255, 255, 255, 0.01);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1);
  position: relative;
  overflow: hidden;
}

.liquid-glass::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1.4px;
  background: linear-gradient(180deg,
    rgba(255,255,255,0.45) 0%, rgba(255,255,255,0.15) 20%,
    rgba(255,255,255,0) 40%, rgba(255,255,255,0) 60%,
    rgba(255,255,255,0.15) 80%, rgba(255,255,255,0.45) 100%);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.grid-line {
  position: fixed;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.05);
  z-index: 1;
  pointer-events: none;
}

.tilted-card-figure {
  position: relative;
  width: 100%;
  height: 100%;
  perspective: 1000px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.tilted-card-inner {
  position: relative;
  transform-style: preserve-3d;
}

.tilted-card-img {
  position: absolute;
  top: 0;
  left: 0;
  object-fit: cover;
  border-radius: 24px;
  will-change: transform;
  transform: translateZ(0);
}

.tilted-card-overlay {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  will-change: transform;
  transform: translateZ(30px);
  width: 100%;
  height: 100%;
  border-radius: 24px;
}

.tilted-card-caption {
  pointer-events: none;
  position: absolute;
  left: 0;
  top: 0;
  border-radius: 4px;
  background-color: #fff;
  padding: 4px 10px;
  font-size: 10px;
  color: #2d2d2d;
  opacity: 0;
  z-index: 3;
}

@media (max-width: 640px) {
  .tilted-card-caption { display: none !important; }
}
`;

// --- TiltedCard ---
const TiltedCard = ({
  imageSrc,
  altText = 'Tilted card image',
  captionText = '',
  containerHeight = '100%',
  containerWidth = '100%',
  imageHeight = '100%',
  imageWidth = '100%',
  scaleOnHover = 1.05,
  rotateAmplitude = 12,
  showTooltip = true,
  overlayContent = null,
  displayOverlayContent = true,
  innerClassName = "tilted-card-inner liquid-glass rounded-3xl border border-white/5 shadow-2xl"
}) => {
  const ref = useRef(null);
  const springValues = { damping: 30, stiffness: 100, mass: 2 };
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useSpring(useMotionValue(0), springValues);
  const rotateY = useSpring(useMotionValue(0), springValues);
  const scale = useSpring(1, springValues);
  const opacity = useSpring(0);
  const rotateFigcaption = useSpring(0, { stiffness: 350, damping: 30, mass: 1 });
  const [lastY, setLastY] = useState(0);

  function handleMouse(e) {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const offsetX = e.clientX - rect.left - rect.width / 2;
    const offsetY = e.clientY - rect.top - rect.height / 2;
    rotateX.set((offsetY / (rect.height / 2)) * -rotateAmplitude);
    rotateY.set((offsetX / (rect.width / 2)) * rotateAmplitude);
    x.set(e.clientX - rect.left);
    y.set(e.clientY - rect.top);
    rotateFigcaption.set(-(offsetY - lastY) * 0.6);
    setLastY(offsetY);
  }

  return (
    <figure
      ref={ref}
      className="tilted-card-figure"
      style={{ height: containerHeight, width: containerWidth }}
      onMouseMove={handleMouse}
      onMouseEnter={() => { scale.set(scaleOnHover); opacity.set(1); }}
      onMouseLeave={() => { opacity.set(0); scale.set(1); rotateX.set(0); rotateY.set(0); rotateFigcaption.set(0); }}
    >
      <motion.div
        className={innerClassName}
        style={{ width: imageWidth, height: imageHeight, rotateX, rotateY, scale }}
      >
        {imageSrc && (
          <motion.img src={imageSrc} alt={altText} className="tilted-card-img" style={{ width: imageWidth, height: imageHeight }} />
        )}
        {imageSrc && (
          <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent z-[1] rounded-[24px] pointer-events-none" />
        )}
        {displayOverlayContent && overlayContent && (
          <motion.div className="tilted-card-overlay">{overlayContent}</motion.div>
        )}
      </motion.div>
      {showTooltip && (
        <motion.figcaption className="tilted-card-caption font-bold tracking-widest uppercase" style={{ x, y, opacity, rotate: rotateFigcaption }}>
          {captionText}
        </motion.figcaption>
      )}
    </figure>
  );
};

// --- LoginModal ---
const LoginModal = ({ isOpen, onClose, onAuthSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState('login'); // 'login' | 'signup'

  const reset = () => { setEmail(''); setPassword(''); setStatus(''); setLoading(false); setMode('login'); };

  const handleClose = () => { reset(); onClose(); };

  const handleEmail = async () => {
    if (!email || !password) { setStatus('Email et mot de passe requis.'); return; }
    setLoading(true); setStatus('');
    try {
      if (mode === 'login') {
        await loginWithEmail(email, password);
        onAuthSuccess?.();
        handleClose();
      } else {
        const msg = await signupWithEmail(email, password);
        setStatus(msg);
        setLoading(false);
      }
    } catch (e) {
      setStatus(e.message);
      setLoading(false);
    }
  };

  const handleGithub = async () => {
    setLoading(true); setStatus('');
    try { await loginWithGithub(); }
    catch (e) { setStatus(e.message); setLoading(false); }
  };

  const handleGoogle = async () => {
    setLoading(true); setStatus('');
    try { await loginWithGoogle(); }
    catch (e) { setStatus(e.message); setLoading(false); }
  };

  const handleGuest = () => {
    getOrCreateGuestId();
    onAuthSuccess?.();
    handleClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[700] flex items-center justify-center p-6">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={handleClose} className="absolute inset-0 bg-black/80 backdrop-blur-md" />
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="relative w-full max-w-md liquid-glass bg-black/60 rounded-[40px] p-10 shadow-2xl border border-white/10"
          >
            <button onClick={handleClose} className="absolute top-6 right-6 p-2 rounded-full hover:bg-white/5 transition-colors text-white/40 hover:text-white">
              <X className="w-5 h-5" />
            </button>
            <div className="text-center mb-8">
              <h2 className="text-4xl font-serif-custom italic text-white mb-2">Rejoindre le Savoir</h2>
              <p className="text-white/40 text-sm">Connectez-vous pour accéder à LoreKeeper.</p>
            </div>

            <div className="space-y-3">
              {/* Toggle login / signup */}
              <div className="flex rounded-full liquid-glass border border-white/5 p-1 mb-2">
                {['login', 'signup'].map(m => (
                  <button key={m} onClick={() => { setMode(m); setStatus(''); }}
                    className={`flex-1 py-2 rounded-full text-[10px] uppercase tracking-widest font-bold transition-all ${mode === m ? 'bg-white text-black' : 'text-white/40 hover:text-white'}`}>
                    {m === 'login' ? 'Connexion' : 'Inscription'}
                  </button>
                ))}
              </div>

              <div className="liquid-glass bg-black/40 rounded-full px-6 py-3 border border-white/5">
                <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="nom@exemple.com"
                  className="w-full bg-transparent border-none outline-none text-white placeholder:text-white/20 text-sm" />
              </div>

              <div className="liquid-glass bg-black/40 rounded-full px-6 py-3 border border-white/5">
                <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="Mot de passe"
                  onKeyDown={e => e.key === 'Enter' && handleEmail()}
                  className="w-full bg-transparent border-none outline-none text-white placeholder:text-white/20 text-sm" />
              </div>

              {status && <p className="text-[11px] text-center px-2" style={{ color: status.includes('créé') ? '#5ed29c' : '#f87171' }}>{status}</p>}

              <button onClick={handleEmail} disabled={loading}
                className="w-full bg-white text-black font-bold py-4 rounded-full hover:scale-[1.02] active:scale-95 transition-all text-sm uppercase tracking-widest shadow-xl disabled:opacity-50">
                {loading ? '...' : mode === 'login' ? 'Se connecter' : "S'inscrire"}
              </button>

              <div className="relative py-2 flex items-center gap-4">
                <div className="flex-1 h-px bg-white/5" />
                <span className="text-[10px] text-white/20 uppercase tracking-widest">ou</span>
                <div className="flex-1 h-px bg-white/5" />
              </div>

              <button onClick={handleGoogle} disabled={loading}
                className="w-full liquid-glass bg-black/40 border border-white/10 flex items-center justify-center gap-3 py-4 rounded-full hover:bg-white/10 transition-all group text-white disabled:opacity-50">
                <GoogleIcon className="w-5 h-5" />
                <span className="text-sm font-medium">Continuer avec Google</span>
              </button>

              <button onClick={handleGithub} disabled={loading}
                className="w-full liquid-glass bg-black/40 border border-white/10 flex items-center justify-center gap-3 py-4 rounded-full hover:bg-white/10 transition-all group text-white disabled:opacity-50">
                <GithubIcon className="w-5 h-5 group-hover:text-[#5ed29c] transition-colors" />
                <span className="text-sm font-medium">Continuer avec GitHub</span>
              </button>

              <button onClick={handleGuest}
                className="w-full text-white/30 hover:text-white/60 text-[11px] uppercase tracking-widest transition-colors py-2">
                Continuer en tant qu'invité
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

// --- VideoBackground ---
const VideoBackground = ({ src, opacityProgress }) => {
  const videoRef = useRef(null);
  const [baseOpacity, setBaseOpacity] = useState(0);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const handleCanPlay = () => {
      video.play();
      let start = null;
      const animate = (ts) => {
        if (!start) start = ts;
        const progress = Math.min((ts - start) / 500, 1);
        setBaseOpacity(progress);
        if (progress < 1) requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);
    };
    video.addEventListener('canplay', handleCanPlay);
    return () => video.removeEventListener('canplay', handleCanPlay);
  }, []);

  return (
    <motion.div style={{ opacity: useTransform(opacityProgress, [0, 0.4], [baseOpacity, 0]) }} className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
      <video ref={videoRef} className="w-full h-full object-cover scale-105" muted autoPlay loop playsInline preload="auto" src={src} />
    </motion.div>
  );
};

// --- Navbar ---
const Navbar = ({ onLoginClick, onTeamClick, onPricingClick, onNavigate, user, onLogout }) => {
  const navigate = useNavigate();
  const go = (path) => { if (onNavigate) onNavigate(path); else navigate(path); };
  return (
    <nav className="fixed top-0 left-0 right-0 z-[500] px-8 py-6 pointer-events-none">
      <div className="pointer-events-auto max-w-7xl mx-auto flex justify-between items-center liquid-glass rounded-full px-8 py-3 border border-white/5">
        <div className="flex items-center gap-12">
          <span className="text-2xl font-serif-custom tracking-tight text-white cursor-pointer" onClick={() => go('/')}>LoreKeeper<sup className="text-[10px] opacity-40 ml-1">®</sup></span>
          <div className="hidden md:flex gap-8 text-[11px] uppercase tracking-[0.2em] font-medium text-white/50">
            <button onClick={() => go('/architecture')} className="hover:text-white transition-colors">Architecture</button>
            <button onClick={onPricingClick} className="hover:text-white transition-colors">Abonnements</button>
            <button onClick={onTeamClick} className="hover:text-white transition-colors">Équipe</button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => go('/monitoring')}
            title="Panel Monitoring"
            className="liquid-glass rounded-full p-2 bg-white/5 hover:bg-white/10 transition-all shadow-lg text-white/40 hover:text-white"
          >
            <Settings className="w-4 h-4" />
          </button>
          {user ? (
            <div className="flex items-center gap-3 ml-1">
              <span className="text-[11px] text-white/40 hidden md:block truncate max-w-[160px]">
                {user.isGuest ? '👤 Invité' : (user.email || 'Connecté')}
              </span>
              <button onClick={onLogout} title="Déconnexion"
                className="liquid-glass rounded-full p-2 bg-white/5 hover:bg-white/10 transition-all shadow-lg text-white/60 hover:text-white">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button onClick={onLoginClick} className="liquid-glass rounded-full px-6 py-2 text-xs uppercase tracking-widest font-bold bg-white/5 hover:bg-white/10 transition-all shadow-lg text-white ml-1">
              Connexion
            </button>
          )}
        </div>
      </div>
    </nav>
  );
};

// --- HeroSection ---
const HeroSection = ({ scrollYProgress }) => {
  const title = "L'ordre dans le chaos.";
  const chars = title.split("");
  const navigate = useNavigate();

  return (
    <section className="relative min-h-screen flex flex-col justify-center items-center pt-32 pb-40 px-6 overflow-hidden">
      <VideoBackground
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4"
        opacityProgress={scrollYProgress}
      />
      <motion.div style={{ opacity: useTransform(scrollYProgress, [0, 0.4], [1, 0]) }} className="absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black z-[1]" />
      <div className="relative z-10 text-center max-w-7xl">
        <h1 className="text-6xl sm:text-8xl md:text-9xl font-serif-custom tracking-tighter leading-[0.85] text-white mb-10">
          {chars.map((c, i) => (
            <motion.span key={i} initial={{ opacity: 0, x: -18 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.03, duration: 0.5 }} className={c === " " ? "mr-4" : ""}>
              {c}
            </motion.span>
          ))}
        </h1>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1, duration: 1 }} className="text-white/50 text-lg md:text-xl max-w-2xl mx-auto font-light leading-relaxed italic mb-16">
          "Concevoir des outils pour les penseurs profonds. Au milieu du chaos, nous bâtissons des havres numériques pour la concentration pure."
        </motion.p>
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 1.2 }} className="flex justify-center">
          <button
            onClick={() => navigate('/chat')}
            className="group flex items-center gap-3 liquid-glass bg-white/5 border border-white/10 text-white font-bold px-10 py-5 rounded-full text-sm uppercase tracking-widest hover:bg-white/10 hover:border-white/20 hover:scale-105 active:scale-95 transition-all shadow-2xl"
          >
            <Sparkles className="w-4 h-4 text-[#5ed29c] group-hover:rotate-12 transition-transform" />
            Interroger le LoreKeeper
            <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
          </button>
        </motion.div>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.5 }} className="mt-6 flex items-center justify-center gap-2 text-white/20 text-[10px] uppercase tracking-widest">
          <span className="w-1.5 h-1.5 rounded-full bg-[#5ed29c] inline-block" />
          RAG · BM25 · Hybrid Search
        </motion.div>
      </div>
    </section>
  );
};

// --- ScrollRevealMessage ---
const WordReveal = ({ word, scrollYProgress, start, end }) => {
  const opacity = useTransform(scrollYProgress, [start, end], [0.1, 1]);
  const scale = useTransform(scrollYProgress, [start, end], [0.95, 1]);
  return (
    <motion.span style={{ opacity, scale }} className="text-4xl md:text-7xl lg:text-8xl font-serif-custom tracking-tighter text-white italic leading-[1.1]">
      {word}
    </motion.span>
  );
};

const ScrollRevealMessage = () => {
  const containerRef = useRef(null);
  const message = "Nous créons un espace où vos données deviennent claires. Le RAG réinventé pour la vitesse absolue et la fiabilité. Que vous soyez un utilisateur régulier ou un passionné connectant des jeux via MCP, notre outil extrait la clarté pure du désordre.";
  const words = message.split(" ");

  const { scrollYProgress } = useScroll({ target: containerRef, offset: ["start end", "end center"] });

  return (
    <section id="manifeste" ref={containerRef} className="bg-black pt-60 pb-20 px-8 relative overflow-hidden">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-wrap gap-x-4 gap-y-4">
          {words.map((word, i) => (
            <WordReveal
              key={i}
              word={word}
              scrollYProgress={scrollYProgress}
              start={i / words.length}
              end={(i + 1) / words.length}
            />
          ))}
        </div>
      </div>
    </section>
  );
};

// --- PricingOverlay ---
const PricingOverlay = ({ isOpen, onClose, navbarProps }) => {
  const plans = [
    { name: 'Gratuit', price: '0€', desc: 'Idéal pour les utilisateurs occasionnels.', features: ['15 requêtes / jour', 'Accès aux archives', 'Moteur RAG standard'] },
    { name: 'Érudit', price: '15€', desc: 'Tout le pouvoir du RAG sur site.', features: ['Requêtes illimitées', 'Analyse multi-documents', 'Vitesse absolue'], highlight: true },
    { name: 'Premium', price: '30€', desc: 'Intégration totale via connecteurs MCP.', features: ['Connecteurs MCP (Jeux)', 'API LoreKeeper', 'Support prioritaire'] }
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[600] bg-black overflow-y-auto">
          <div className="fixed inset-0 z-0 pointer-events-none">
            <video className="w-full h-full object-cover opacity-40 grayscale" src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4" muted autoPlay loop playsInline />
            <div className="absolute inset-0 bg-gradient-to-b from-black/80 via-black/40 to-black" />
          </div>
          {navbarProps && <Navbar {...navbarProps} />}
          <div className="relative z-10 max-w-7xl w-full mx-auto px-6 flex flex-col justify-center pb-12 pt-32">
            <div className="flex flex-col md:flex-row justify-between items-end mb-8 border-b border-white/10 pb-6">
              <h2 className="text-5xl md:text-7xl font-serif-custom text-white tracking-tighter">Abonnements. <br /><em className="italic text-white/40">Vitesse absolue.</em></h2>
              <p className="text-white/40 text-right max-w-xs text-[10px] uppercase tracking-[0.4em] mt-4">Fiabilité totale. <br /> Pour les explorateurs et les créateurs.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {plans.map((plan, i) => (
                <motion.div key={plan.name} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.1 }} className="w-full">
                  <TiltedCard
                    containerHeight="500px" imageHeight="500px"
                    scaleOnHover={1.02} rotateAmplitude={6}
                    showTooltip={false} displayOverlayContent={true}
                    innerClassName={`tilted-card-inner liquid-glass rounded-[48px] border border-white/5 w-full h-full flex flex-col ${plan.highlight ? 'bg-white/10 ring-1 ring-[#5ed29c]/30 shadow-[0_0_50px_rgba(94,210,156,0.1)]' : 'bg-black/40'}`}
                    overlayContent={
                      <div className="p-8 flex flex-col h-full pointer-events-auto">
                        <h3 className="text-2xl font-serif-custom italic text-white mb-1">{plan.name}</h3>
                        <div className="mb-4 flex items-baseline">
                          <span className="text-4xl font-bold text-white">{plan.price}</span>
                          <span className="text-white/20 text-xs ml-2">/ mois</span>
                        </div>
                        <p className="text-white/50 text-xs mb-6 leading-relaxed">{plan.desc}</p>
                        <div className="space-y-3 mb-6 flex-1">
                          {plan.features.map(f => (
                            <div key={f} className="flex items-center gap-2 text-xs text-white/70">
                              <Check className="w-3 h-3 text-[#5ed29c] shrink-0" />{f}
                            </div>
                          ))}
                        </div>
                        <button className={`w-full py-3 rounded-full text-[10px] font-bold uppercase tracking-widest transition-all mt-auto ${plan.highlight ? 'bg-[#5ed29c] text-black hover:brightness-110' : 'liquid-glass border border-white/10 text-white hover:bg-white/5'}`}>Choisir</button>
                      </div>
                    }
                  />
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// --- TeamOverlay ---
const TeamOverlay = ({ isOpen, onClose, navbarProps }) => {
  const team = [
    { name: 'Emir', github: '#', linkedin: '#' },
    { name: 'Ediz', github: '#', linkedin: '#' },
    { name: 'Nicols', github: '#', linkedin: '#' },
    { name: 'Tom', github: '#', linkedin: '#' },
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[600] bg-black overflow-hidden flex flex-col">
          <div className="fixed inset-0 z-0 pointer-events-none">
            <video className="w-full h-full object-cover opacity-40" src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4" muted autoPlay loop playsInline />
            <div className="absolute inset-0 bg-gradient-to-b from-black/80 via-black/40 to-black" />
          </div>
          {navbarProps && <Navbar {...navbarProps} />}
          <div className="relative z-10 flex-1 max-w-7xl w-full mx-auto px-6 flex flex-col justify-center pb-12 pt-32">
            <div className="flex flex-col md:flex-row justify-between items-end mb-12 border-b border-white/10 pb-8">
              <h2 className="text-5xl md:text-7xl font-serif-custom text-white tracking-tighter">The LoreKeepers. <br /><em className="italic text-white/40">Guiding light.</em></h2>
              <p className="text-white/40 text-right max-w-xs text-[10px] uppercase tracking-[0.4em] mt-8">Architects of the digital void. <br /> Designing the future of RAG.</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {team.map((member, i) => (
                <motion.div key={member.name} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.15 }} className="aspect-[4/5] w-full group">
                  <TiltedCard
                    altText={`Portrait pour ${member.name}`}
                    captionText={`LoreKeeper - ${member.name}`}
                    scaleOnHover={1.05} rotateAmplitude={12}
                    showTooltip={true} displayOverlayContent={true}
                    overlayContent={
                      <div className="flex flex-col justify-end p-8 h-full w-full pointer-events-auto">
                        <div className="absolute top-8 right-8 flex flex-col gap-3 opacity-0 group-hover:opacity-100 translate-y-2 group-hover:translate-y-0 transition-all duration-300">
                          <a href={member.linkedin} className="p-3 rounded-full liquid-glass hover:text-[#5ed29c] transition-colors"><LinkedinIcon className="w-5 h-5" /></a>
                          <a href={member.github} className="p-3 rounded-full liquid-glass hover:text-[#5ed29c] transition-colors"><GithubIcon className="w-5 h-5" /></a>
                        </div>
                        <h3 className="text-white text-3xl font-serif-custom italic drop-shadow-md">{member.name}</h3>
                      </div>
                    }
                  />
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// --- ArchitecturePage ---

const FadeInSection = ({ children, delay = 0, className = "" }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 32 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.65, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

const PipelineStep = ({ icon: Icon, step, title, desc, color = "#5ed29c", delay = 0 }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, x: -24 }}
      animate={isInView ? { opacity: 1, x: 0 } : {}}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      className="flex gap-5 items-start group"
    >
      <div className="relative shrink-0 flex flex-col items-center">
        <div
          className="w-11 h-11 rounded-2xl flex items-center justify-center border transition-all duration-300 group-hover:scale-110"
          style={{ background: `${color}12`, borderColor: `${color}30` }}
        >
          <Icon size={18} style={{ color }} />
        </div>
        <div className="w-px flex-1 mt-3" style={{ background: `linear-gradient(to bottom, ${color}30, transparent)`, minHeight: 32 }} />
      </div>
      <div className="pb-8">
        <div className="text-[9px] uppercase tracking-[0.3em] mb-1" style={{ color: `${color}80` }}>Étape {step}</div>
        <h4 className="text-[15px] font-semibold text-white mb-1.5">{title}</h4>
        <p className="text-[13px] text-white/45 leading-relaxed">{desc}</p>
      </div>
    </motion.div>
  );
};

const CompareCard = ({ title, items, accent, icon: Icon, delay = 0 }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 28 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
      className="liquid-glass rounded-[32px] border p-8 flex flex-col gap-5"
      style={{ borderColor: `${accent}20` }}
    >
      <div className="flex items-center gap-3 mb-1">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${accent}15` }}>
          <Icon size={16} style={{ color: accent }} />
        </div>
        <h3 className="text-[16px] font-semibold text-white">{title}</h3>
      </div>
      <ul className="space-y-3">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-3">
            <span className="mt-[6px] text-[5px] shrink-0" style={{ color: accent }}>●</span>
            <span className="text-[13px] text-white/55 leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </motion.div>
  );
};

const StatPill = ({ value, label, delay = 0 }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, scale: 0.88 }}
      animate={isInView ? { opacity: 1, scale: 1 } : {}}
      transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }}
      className="liquid-glass border border-white/[0.07] rounded-[24px] px-8 py-6 text-center"
    >
      <div className="text-3xl font-bold text-[#5ed29c] mb-1">{value}</div>
      <div className="text-[11px] uppercase tracking-widest text-white/30">{label}</div>
    </motion.div>
  );
};

const TechCard = ({ tech, delay = 0 }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 16 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.45, delay, ease: [0.22, 1, 0.36, 1] }}
      className="liquid-glass border border-white/[0.06] rounded-[20px] p-5 group hover:border-white/10 transition-all"
    >
      <div className="text-[9px] uppercase tracking-[0.25em] mb-2" style={{ color: `${tech.color}70` }}>{tech.label}</div>
      <div className="text-[15px] font-semibold text-white/80 group-hover:text-white transition-colors">{tech.value}</div>
      <div className="mt-3 h-[2px] w-8 rounded-full transition-all duration-300 group-hover:w-full" style={{ background: `linear-gradient(to right, ${tech.color}60, transparent)` }} />
    </motion.div>
  );
};

const ArchitecturePage = () => {
  const navigate = useNavigate();

  const pipeline = [
    {
      icon: Search,
      title: "Recherche Hybride",
      desc: "La question est traitée en parallèle par deux moteurs : une recherche vectorielle sémantique (Qdrant) et BM25 (exact token matching). Les scores sont fusionnés par l'algorithme RRF pour maximiser la précision.",
      color: "#5ed29c",
    },
    {
      icon: Brain,
      title: "Reformulation Contextuelle",
      desc: "Si la question contient des anaphores (\"il\", \"elle\", \"ça\"…), un modèle Groq léger la reformule en 200ms en s'appuyant sur l'historique de conversation — sans jamais l'inventer.",
      color: "#60a5fa",
    },
    {
      icon: Layers,
      title: "Re-ranking Intelligent",
      desc: "Un cross-encoder analyse les passages récupérés et les réordonne par pertinence réelle. Si le top-1 est déjà très confiant, le reranker est sauté pour gagner du temps.",
      color: "#a78bfa",
    },
    {
      icon: Shield,
      title: "Sécurité & Masquage PII",
      desc: "Chaque réponse passe par un filtre regex anti-PII (emails, téléphones) et un juge LLM autonome qui détecte les hallucinations, injections de prompt et contenus hors-sujet.",
      color: "#f87171",
    },
    {
      icon: Zap,
      title: "Génération en Streaming",
      desc: "Le LLM principal (DeepSeek/OpenRouter) streame les tokens en temps réel. En cas de 429 ou d'erreur, la chaîne bascule automatiquement sur Groq puis sur un modèle OpenRouter gratuit.",
      color: "#fbbf24",
    },
    {
      icon: BarChart3,
      title: "Observabilité Complète",
      desc: "Chaque requête est tracée dans Langfuse (latence, modèle, fallback, score juge). Les feedbacks utilisateur (👍/👎) sont remontés et la mémoire long-terme est résumée par LLM.",
      color: "#34d399",
    },
  ];

  const ragVsClassic = [
    {
      title: "IA Classique (ChatGPT, etc.)",
      accent: "#f87171",
      icon: Brain,
      items: [
        "Répond depuis la mémoire du modèle — figée à la date d'entraînement.",
        "Invente plausiblement des faits qui n'existent pas (hallucination).",
        "Aucune référence vérifiable aux sources originales.",
        "Contexte universel et non personnalisé — ne connaît pas votre lore.",
        "Impossible d'ajouter de nouvelles données sans re-entraîner.",
      ],
    },
    {
      title: "LoreKeeper RAG",
      accent: "#5ed29c",
      icon: Database,
      items: [
        "Répond uniquement depuis vos documents indexés — jamais en dehors.",
        "Chaque affirmation est ancrée dans un passage source citable.",
        "Recherche hybride (vecteurs + BM25) pour ne rater aucune correspondance.",
        "Mémoire long-terme par utilisateur — le contexte s'enrichit à chaque session.",
        "Ajout de lore en temps réel via l'ingestion — sans toucher au modèle.",
      ],
    },
  ];

  const techStack = [
    { label: "Vector DB", value: "Qdrant", color: "#5ed29c" },
    { label: "Search", value: "BM25 + RRF", color: "#60a5fa" },
    { label: "LLM", value: "DeepSeek / Groq", color: "#a78bfa" },
    { label: "Reranker", value: "Cross-encoder", color: "#fbbf24" },
    { label: "Tracing", value: "Langfuse", color: "#f87171" },
    { label: "Auth", value: "Supabase", color: "#34d399" },
    { label: "Protocol", value: "MCP (stdio/SSE)", color: "#fb923c" },
    { label: "Cache", value: "Redis Semantic", color: "#e879f9" },
  ];

  return (
    <div className="relative min-h-screen">
      {/* Ambient blobs */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <motion.div
          className="absolute top-[-10%] left-[20%] w-[700px] h-[700px] rounded-full blur-[160px]"
          style={{ background: "radial-gradient(circle, rgba(94,210,156,0.07) 0%, transparent 70%)" }}
          animate={{ x: [0, 40, -20, 0], y: [0, -30, 40, 0] }}
          transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute bottom-[10%] right-[10%] w-[500px] h-[500px] rounded-full blur-[140px]"
          style={{ background: "radial-gradient(circle, rgba(96,165,250,0.06) 0%, transparent 70%)" }}
          animate={{ x: [0, -50, 30, 0], y: [0, 50, -20, 0] }}
          transition={{ duration: 28, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-40 pb-32">

        {/* Hero */}
        <FadeInSection className="mb-24 text-center">
          <div className="inline-flex items-center gap-2 liquid-glass border border-white/[0.07] rounded-full px-5 py-2 mb-8">
            <GitBranch size={12} className="text-[#5ed29c]" />
            <span className="text-[10px] uppercase tracking-[0.3em] text-white/40">Architecture Technique</span>
          </div>
          <h1 className="text-6xl md:text-8xl font-serif-custom tracking-tighter leading-[0.88] text-white mb-8">
            Pas une IA.<br />
            <em className="italic text-white/40">Un oracle.</em>
          </h1>
          <p className="text-white/40 text-lg max-w-2xl mx-auto leading-relaxed font-light">
            LoreKeeper ne devine pas. Il consulte. Chaque réponse est construite depuis des documents réels,
            vérifiée contre des sources traçables, et filtrée par un juge autonome.
          </p>
        </FadeInSection>

        {/* Stats */}
        <FadeInSection className="mb-24">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatPill value="< 700ms" label="P50 latence" delay={0} />
            <StatPill value="4 niveaux" label="Fallback LLM" delay={0.08} />
            <StatPill value="Hybride" label="Recherche BM25 + Vector" delay={0.16} />
            <StatPill value="100%" label="Sources citées" delay={0.24} />
          </div>
        </FadeInSection>

        {/* Pipeline */}
        <FadeInSection className="mb-24">
          <div className="mb-10">
            <div className="text-[10px] uppercase tracking-[0.3em] text-[#5ed29c]/60 mb-3">Pipeline RAG</div>
            <h2 className="text-4xl md:text-5xl font-serif-custom tracking-tighter text-white">Comment ça fonctionne</h2>
          </div>
          <div className="liquid-glass border border-white/[0.05] rounded-[40px] p-8 md:p-12">
            {pipeline.map((step, i) => (
              <PipelineStep
                key={i}
                icon={step.icon}
                step={i + 1}
                title={step.title}
                desc={step.desc}
                color={step.color}
                delay={i * 0.08}
              />
            ))}
          </div>
        </FadeInSection>

        {/* RAG vs Classic */}
        <FadeInSection className="mb-24">
          <div className="mb-10">
            <div className="text-[10px] uppercase tracking-[0.3em] text-[#60a5fa]/60 mb-3">Comparaison</div>
            <h2 className="text-4xl md:text-5xl font-serif-custom tracking-tighter text-white">Pourquoi c'est différent</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {ragVsClassic.map((card, i) => (
              <CompareCard key={i} {...card} delay={i * 0.12} />
            ))}
          </div>
        </FadeInSection>

        {/* Tech Stack */}
        <FadeInSection className="mb-24">
          <div className="mb-10">
            <div className="text-[10px] uppercase tracking-[0.3em] text-[#a78bfa]/60 mb-3">Stack Technologique</div>
            <h2 className="text-4xl md:text-5xl font-serif-custom tracking-tighter text-white">Construit pour durer</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {techStack.map((tech, i) => (
              <TechCard key={i} tech={tech} delay={i * 0.06} />
            ))}
          </div>
        </FadeInSection>

        {/* CTA */}
        <FadeInSection className="text-center">
          <div className="liquid-glass border border-white/[0.06] rounded-[40px] p-12 md:p-16 relative overflow-hidden">
            <motion.div
              className="absolute inset-0 rounded-[40px] pointer-events-none"
              style={{ background: "radial-gradient(ellipse at 50% 0%, rgba(94,210,156,0.06) 0%, transparent 60%)" }}
            />
            <h2 className="text-4xl md:text-6xl font-serif-custom tracking-tighter text-white mb-5 relative z-10">
              Prêt à interroger l'Oracle ?
            </h2>
            <p className="text-white/35 mb-10 max-w-lg mx-auto text-[15px] leading-relaxed relative z-10">
              Pose une question sur le lore d'Aethelgard. L'Oracle consulte les archives, cite ses sources, et ne te mentira jamais.
            </p>
            <button
              onClick={() => navigate('/chat')}
              className="relative z-10 group inline-flex items-center gap-3 liquid-glass bg-white/5 border border-white/10 text-white font-bold px-10 py-5 rounded-full text-sm uppercase tracking-widest hover:bg-white/10 hover:border-white/20 hover:scale-105 active:scale-95 transition-all shadow-2xl"
            >
              <Sparkles className="w-4 h-4 text-[#5ed29c] group-hover:rotate-12 transition-transform" />
              Interroger LoreKeeper
              <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            </button>
          </div>
        </FadeInSection>
      </div>
    </div>
  );
};

// --- Footer ---
const Footer = () => (
  <footer className="bg-black pt-20 pb-12 px-10 border-t border-white/5 relative z-10">
    <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-end gap-12">
      <div>
        <h2 className="text-7xl md:text-9xl font-serif-custom text-white tracking-tighter mb-6">LoreKeeper</h2>
        <p className="text-white/20 tracking-[0.4em] uppercase text-[10px]">Architects of the digital knowledge</p>
      </div>
      <div className="text-right">
        <p className="text-white/40 mb-8 max-w-xs ml-auto text-sm italic">"Order emerging from chaos. Every word recorded, every insight found."</p>
      </div>
    </div>
    <div className="max-w-7xl mx-auto mt-20 pt-12 border-t border-white/5 flex flex-col md:flex-row justify-between text-[10px] uppercase tracking-[0.4em] text-white/20 gap-4">
      <span>© 2026 LoreKeeper Team — Emir, Ediz, Nicols, Tom</span>
      <div className="flex gap-8">
        <a href="#" className="hover:text-white transition-colors">Privacy</a>
        <a href="#" className="hover:text-white transition-colors">Terms</a>
        <a href="#" className="hover:text-white transition-colors">GitHub</a>
      </div>
    </div>
  </footer>
);

// --- App ---
export default function App() {
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [isTeamOpen, setIsTeamOpen] = useState(false);
  const [isPricingOpen, setIsPricingOpen] = useState(false);
  const [user, setUser] = useState(null); // { email, isGuest } | null
  const { scrollYProgress } = useScroll();
  const location = useLocation();
  const navigate = useNavigate();

  // Initialisation auth au montage
  useEffect(() => {
    // Vérifier session Supabase active (ex: retour OAuth GitHub)
    getSession().then(session => {
      if (session?.user) {
        setUser({ email: session.user.email, isGuest: false });
      } else {
        // Vérifier mode invité
        const guestId = localStorage.getItem('oracleGuestId');
        if (guestId) setUser({ email: null, isGuest: true });
      }
    });

    // Écouter les changements de session (login / logout / OAuth callback)
    const unsub = onAuthStateChange(supaUser => {
      if (supaUser) {
        localStorage.removeItem('oracleGuestId');
        setUser({ email: supaUser.email, isGuest: false });
        setIsLoginOpen(false);
      } else {
        // Garder le mode invité s'il existe
        const guestId = localStorage.getItem('oracleGuestId');
        setUser(guestId ? { email: null, isGuest: true } : null);
      }
    });
    return unsub;
  }, []);

  // Ouvrir le login modal si on arrive depuis une redirection /chat
  useEffect(() => {
    if (location.state?.openLogin) {
      setIsLoginOpen(true);
    }
  }, [location.state]);

  const handleAuthSuccess = useCallback(() => {
    const guestId = localStorage.getItem('oracleGuestId');
    if (guestId) {
      setUser({ email: null, isGuest: true });
      setIsLoginOpen(false);
    }
    // Si Supabase → onAuthStateChange s'en charge
  }, []);

  const handleLogout = useCallback(async () => {
    await logout();
    setUser(null);
  }, []);

  const closeAll = useCallback(() => {
    setIsTeamOpen(false);
    setIsPricingOpen(false);
    setIsLoginOpen(false);
  }, []);

  const handleNavigate = useCallback((path) => {
    closeAll();
    navigate(path);
  }, [closeAll, navigate]);

  const openTeam = useCallback(() => {
    setIsPricingOpen(false);
    setIsLoginOpen(false);
    setIsTeamOpen(true);
  }, []);

  const openPricing = useCallback(() => {
    setIsTeamOpen(false);
    setIsLoginOpen(false);
    setIsPricingOpen(true);
  }, []);

  const openLogin = useCallback(() => {
    setIsTeamOpen(false);
    setIsPricingOpen(false);
    setIsLoginOpen(true);
  }, []);

  return (
    <Routes>
      {/* ── Panel Monitoring ─────────────────────────────── */}
      <Route path="/monitoring" element={<MonitoringRoute />} />

      {/* ── Page Chat ────────────────────────────────────── */}
      <Route path="/chat" element={
        <ChatRoute user={user} onLogout={handleLogout} onLoginOpen={() => setIsLoginOpen(true)} />
      } />

      {/* ── Architecture ─────────────────────────────────── */}
      <Route path="/architecture" element={
        <div className="relative bg-black" style={{ WebkitUserSelect: 'none' }}>
          <style dangerouslySetInnerHTML={{ __html: styles }} />
          <Navbar
            onLoginClick={openLogin}
            onTeamClick={openTeam}
            onPricingClick={openPricing}
            onNavigate={handleNavigate}
            user={user}
            onLogout={handleLogout}
          />
          <ArchitecturePage />
          <Footer />
          <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} onAuthSuccess={handleAuthSuccess} />

          <TeamOverlay isOpen={isTeamOpen} onClose={() => setIsTeamOpen(false)} navbarProps={{ onLoginClick: openLogin, onTeamClick: openTeam, onPricingClick: openPricing, onNavigate: handleNavigate, user, onLogout: handleLogout }} />
          <PricingOverlay isOpen={isPricingOpen} onClose={() => setIsPricingOpen(false)} navbarProps={{ onLoginClick: openLogin, onTeamClick: openTeam, onPricingClick: openPricing, onNavigate: handleNavigate, user, onLogout: handleLogout }} />
        </div>
      } />

      {/* ── Landing (toutes les autres routes) ───────────── */}
      <Route path="*" element={
        <div className="relative bg-black" style={{ WebkitUserSelect: 'none' }}>
          <style dangerouslySetInnerHTML={{ __html: styles }} />

          <div className="grid-line" style={{ left: '25%' }} />
          <div className="grid-line" style={{ left: '50%' }} />
          <div className="grid-line" style={{ left: '75%' }} />

          <Navbar
            onLoginClick={openLogin}
            onTeamClick={openTeam}
            onPricingClick={openPricing}
            onNavigate={handleNavigate}
            user={user}
            onLogout={handleLogout}
          />
          <HeroSection scrollYProgress={scrollYProgress} />
          <ScrollRevealMessage />
          <Footer />

          <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} onAuthSuccess={handleAuthSuccess} />

          <TeamOverlay isOpen={isTeamOpen} onClose={() => setIsTeamOpen(false)} navbarProps={{ onLoginClick: openLogin, onTeamClick: openTeam, onPricingClick: openPricing, onNavigate: handleNavigate, user, onLogout: handleLogout }} />
          <PricingOverlay isOpen={isPricingOpen} onClose={() => setIsPricingOpen(false)} navbarProps={{ onLoginClick: openLogin, onTeamClick: openTeam, onPricingClick: openPricing, onNavigate: handleNavigate, user, onLogout: handleLogout }} />
        </div>
      } />
    </Routes>
  );
}

// ── Route /chat — protégée : redirige vers / si non authentifié ─────────────
function ChatRoute({ user, onLogout, onLoginOpen }) {
  const location = useLocation();
  const navigate = useNavigate();
  const initialQuestion = location.state?.question ?? null;

  // user === null → pas encore résolu (loading), undefined → résolu non connecté
  // On attend la résolution pour éviter un flash de redirection
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    // Attendre que l'init auth soit terminée (getSession est async)
    const timer = setTimeout(() => setAuthChecked(true), 300);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (authChecked && !user) {
      // Redirige vers la landing et ouvre le modal de connexion
      navigate('/', { replace: true, state: { openLogin: true } });
    }
  }, [authChecked, user, navigate]);

  if (!user) return null;

  return (
    <ChatPage
      user={user}
      onLogout={onLogout}
      initialQuestion={initialQuestion}
    />
  );
}
