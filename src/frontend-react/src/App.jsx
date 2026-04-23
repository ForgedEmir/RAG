import React, { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';

import { Routes, Route, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence, useTransform, useMotionValue, useSpring } from 'framer-motion';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
gsap.registerPlugin(ScrollTrigger);
import { ArrowUpRight, Sparkles, X, Check, LogOut, Settings, Database, Search, Brain, Zap, GitBranch, Shield, BarChart3, Layers, MessageSquare } from 'lucide-react';
import {
  loginWithEmail, signupWithEmail, loginWithGithub, loginWithGoogle,
  logout, getSession, onAuthStateChange, getOrCreateGuestId,
} from './auth.js';
import ChatPage from './ChatPage.jsx';
import MonitoringRoute from './MonitoringPage.jsx';
import DocsPage from './DocsPage.jsx';
// ── Lenis + ScrollTrigger cleanup on route change ───────────────────────────
// POURQUOI 3 phases :
// • useLayoutEffect (sync, avant paint) : kill GSAP pin → évite l'écran noir
//   GSAP pin:true met overflow:hidden sur <html>. Si on attend useEffect,
//   le browser peint déjà la page avec overflow:hidden → écran noir.
// • useEffect Lenis : cycle de vie Lenis (landing only), ticker nommé → pas de fuite
// • useEffect phase 3 : cleanup résiduel après ctx.revert() de PinnedReveal
const LenisReset = () => {
  const location = useLocation();
  const lenisRef    = useRef(null);
  const tickerFnRef = useRef(null);

  // Phase 1 — synchrone, avant le premier paint ─────────────────────────────
  useLayoutEffect(() => {
    ScrollTrigger.getAll().forEach(st => st.kill());
    ScrollTrigger.clearScrollMemory();

    document.querySelectorAll('.pin-spacer').forEach(el => {
      const child = el.children[0];
      if (child) { child.style.cssText = ''; el.parentNode.insertBefore(child, el); }
      el.remove();
    });

    document.body.style.cssText = '';
    document.documentElement.style.cssText = '';
    const root = document.getElementById('root');
    if (root) root.removeAttribute('style');

    window.scrollTo(0, 0);
  }, [location.pathname]);

  // Phase 2 — cycle de vie Lenis (landing uniquement) ───────────────────────
  useEffect(() => {
    if (location.pathname !== '/') return;

    const lenis = new Lenis({ lerp: 0.08, smoothWheel: true });
    lenisRef.current = lenis;
    window.__lenis = lenis; // expose pour pause/resume depuis App

    const tickerFn = (time) => lenis.raf(time * 1000);
    tickerFnRef.current = tickerFn;
    gsap.ticker.add(tickerFn);
    gsap.ticker.lagSmoothing(0);

    lenis.on('scroll', ScrollTrigger.update);
    ScrollTrigger.scrollerProxy(document.documentElement, {
      scrollTop: (v) => (v !== undefined ? lenis.scrollTo(v) : lenis.scroll),
      getBoundingClientRect: () => ({ top: 0, left: 0, width: window.innerWidth, height: window.innerHeight }),
    });

    requestAnimationFrame(() => ScrollTrigger.refresh());

    return () => {
      if (tickerFnRef.current) {
        gsap.ticker.remove(tickerFnRef.current);
        tickerFnRef.current = null;
      }
      lenis.destroy();
      lenisRef.current = null;
      window.__lenis = null;
      ScrollTrigger.scrollerProxy(document.documentElement, null);
    };
  }, [location.pathname]);

  // Phase 3 — après ctx.revert() de PinnedReveal (useEffect cleanup enfant) ─
  useEffect(() => {
    if (location.pathname === '/') return;
    document.body.style.overflow = '';
    document.body.style.transform = '';
    document.documentElement.style.overflow = '';
    document.documentElement.style.transform = '';
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return null;
};

// ── Cursor Glow ──────────────────────────────────────────────────────────────
const CursorGlow = () => {
  const rawX = useMotionValue(-400);
  const rawY = useMotionValue(-400);
  const springX = useSpring(rawX, { stiffness: 80, damping: 20 });
  const springY = useSpring(rawY, { stiffness: 80, damping: 20 });
  // Derived transforms at top level — never inside JSX
  const x = useTransform(springX, v => v - 240);
  const y = useTransform(springY, v => v - 240);

  useEffect(() => {
    const move = (e) => { rawX.set(e.clientX); rawY.set(e.clientY); };
    window.addEventListener('mousemove', move);
    return () => window.removeEventListener('mousemove', move);
  }, [rawX, rawY]);

  return (
    <motion.div
      className="fixed top-0 left-0 pointer-events-none z-[9999] mix-blend-screen"
      style={{
        x,
        y,
        width: 480,
        height: 480,
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(245,158,11,0.10) 0%, rgba(245,158,11,0.03) 40%, transparent 70%)',
      }}
    />
  );
};

// Brand icons not available in lucide-react
const LinkedinIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" /><rect x="2" y="9" width="4" height="12" /><circle cx="4" cy="4" r="2" />
  </svg>
);

const GithubIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" /><path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);

const GoogleIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
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
  --primary: #F59E0B;
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
              <h2 className="text-4xl font-serif-custom italic text-white mb-2">Accéder à DocOracle</h2>
              <p className="text-white/40 text-sm">Connectez-vous pour interroger votre documentation.</p>
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

              {status && <p className="text-[11px] text-center px-2" style={{ color: status.includes('créé') ? '#F59E0B' : '#f87171' }}>{status}</p>}

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
                <GithubIcon className="w-5 h-5 group-hover:text-[#F59E0B] transition-colors" />
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
const Navbar = ({ onLoginClick, onPricingClick, onDocsClick, onArchitectureClick, onNavigate, user, onLogout }) => {
  const navigate = useNavigate();
  const go = (path) => { if (onNavigate) onNavigate(path); else navigate(path); };
  return (
    <nav className="fixed top-0 left-0 right-0 z-[500] px-8 py-6 pointer-events-none">
      <div className="pointer-events-auto max-w-7xl mx-auto flex justify-between items-center liquid-glass rounded-full px-8 py-3 border border-white/5">
        <div className="flex items-center gap-12">
          <span className="text-2xl font-serif-custom tracking-tight text-white cursor-pointer" onClick={() => go('/')}>DocOracle<sup className="text-[10px] opacity-40 ml-1">®</sup></span>
          <div className="hidden md:flex gap-8 text-[11px] uppercase tracking-[0.2em] font-medium text-white/50">
            <button onClick={() => go('/')} className="hover:text-white transition-colors">Accueil</button>
            <button onClick={onArchitectureClick ?? (() => go('/architecture'))} className="hover:text-white transition-colors">Architecture</button>
            <button onClick={onDocsClick ?? (() => go('/docs'))} className="hover:text-white transition-colors">Documentation</button>
            <button onClick={onPricingClick} className="hover:text-white transition-colors">Abonnements</button>
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
const HeroSection = () => {
  const title = "Vos docs. Des réponses.";
  const chars = title.split("");
  const navigate = useNavigate();

  return (
    <section className="relative min-h-screen flex items-center justify-center px-6 md:px-12 overflow-hidden">
      {/* Full-page video background */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
        <video
          className="absolute inset-0 w-full h-full object-cover"
          style={{ filter: 'blur(10px)', transform: 'scale(1.08)' }}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4"
          muted autoPlay loop playsInline
        />
        <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.52)' }} />
      </div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-48 z-[2] pointer-events-none"
        style={{ background: 'linear-gradient(to bottom, transparent, #000000)' }} />

      {/* Centered content */}
      <div className="relative z-10 w-full max-w-4xl mx-auto text-center pt-24 pb-16">

        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.5 }}
          className="inline-flex items-center gap-2 mb-8 px-4 py-1.5 rounded-full border border-white/[0.08] bg-white/[0.02]"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] inline-block" />
          <span className="text-[9px] uppercase tracking-[0.4em] text-[#F59E0B]/70 font-mono">
            RAG · BM25 · Hybrid Search · Production-grade
          </span>
        </motion.div>

        <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl font-serif-custom tracking-tighter leading-[0.85] text-white mb-8" style={{letterSpacing:'-0.03em'}}>
          {chars.map((c, i) => (
            <motion.span
              key={i}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 + i * 0.028, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className={c === " " ? "mr-[0.25em]" : ""}
            >
              {c}
            </motion.span>
          ))}
        </h1>

        <motion.p
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          transition={{ delay: 1.1, duration: 0.9 }}
          className="text-white/50 text-sm md:text-[15px] max-w-xl mx-auto font-light leading-relaxed mb-10 tracking-wide"
        >
          Moteur RAG hybride — indexez n'importe quelle documentation, interrogez-la en langage naturel, obtenez des réponses sourcées en moins de 500ms.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1.3, ease: [0.16, 1, 0.3, 1] }}
          className="flex justify-center"
        >
          <button
            onClick={() => navigate('/chat')}
            className="group flex items-center gap-3 liquid-glass bg-white/5 border border-white/10 text-white font-bold px-9 py-4 rounded-full text-sm uppercase tracking-widest hover:bg-white/10 hover:border-white/20 hover:scale-105 active:scale-95 transition-all shadow-2xl"
          >
            <Sparkles className="w-4 h-4 text-[#F59E0B] group-hover:rotate-12 transition-transform" />
            Essayer maintenant
            <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
          </button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          transition={{ delay: 1.6 }}
          className="mt-8 flex flex-wrap items-center justify-center gap-2"
        >
          {['OpenRouter', 'Qdrant', 'Langfuse', 'FastAPI', 'SSE'].map((tag) => (
            <span key={tag} className="px-3 py-1 rounded-full text-[9px] uppercase tracking-[0.2em] text-white/25 border border-white/[0.06] font-mono">
              {tag}
            </span>
          ))}
        </motion.div>
      </div>
    </section>
  );
};

// --- PinnedReveal (GSAP ScrollTrigger — remplace ScrollRevealMessage) ---
const PinnedReveal = () => {
  const containerRef = useRef(null);
  const words = [
    "Vos", "docs.", "Vos", "données.", "Vos", "réponses.",
    "Sourcées.", "Vérifiées.", "En", "moins", "de", "500ms."
  ];

  useEffect(() => {
    const ctx = gsap.context(() => {
      // Ligne centrale — s'étend pendant le scroll pincé
      gsap.fromTo('.pinned-line',
        { scaleY: 0 },
        {
          scaleY: 1,
          ease: 'none',
          scrollTrigger: {
            trigger: containerRef.current,
            start: 'top top',
            end: '+=1200',
            scrub: 0.6,
            pin: true,
            pinSpacing: true,
            anticipatePin: 1,
            onLeaveBack: () => {
              document.body.style.overflow = '';
              document.documentElement.style.overflow = '';
            },
          },
        }
      );

      // Mots — s'allument un par un pendant le scroll
      gsap.fromTo('.reveal-word',
        { opacity: 0.08, y: 12 },
        {
          opacity: 1,
          y: 0,
          stagger: 0.12,
          ease: 'none',
          scrollTrigger: {
            trigger: containerRef.current,
            start: 'top top',
            end: '+=1200',
            scrub: 0.8,
          },
        }
      );
    }, containerRef);

    return () => {
      ctx.revert();
      // Kill any remaining triggers and restore DOM state
      ScrollTrigger.getAll().forEach(st => st.kill());
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
      window.scrollTo(0, 0);
    };
  }, []);

  return (
    <section
      ref={containerRef}
      className="relative bg-black flex items-center justify-center min-h-screen px-8 overflow-hidden"
    >
      {/* Ligne verticale centrale */}
      <div
        className="pinned-line absolute left-1/2 top-0 bottom-0 w-px origin-top pointer-events-none"
        style={{ background: 'linear-gradient(to bottom, transparent, rgba(245,158,11,0.25), transparent)' }}
      />

      <div className="relative z-10 max-w-5xl mx-auto text-center">
        <div className="text-[9px] uppercase tracking-[0.45em] text-[#F59E0B]/50 mb-12 font-mono">
          Ce que fait DocOracle
        </div>

        <div className="flex flex-wrap justify-center gap-x-5 gap-y-3">
          {words.map((word, i) => (
            <span
              key={i}
              className={`reveal-word inline-block font-serif-custom tracking-tighter leading-[1.05] select-none ${word.endsWith('.') || word === '+'
                ? 'text-[#F59E0B] text-5xl md:text-7xl lg:text-8xl'
                : 'text-white text-5xl md:text-7xl lg:text-8xl'
                }`}
            >
              {word}
            </span>
          ))}
        </div>

        <div className="mt-16 text-[11px] text-white/20 tracking-[0.3em] uppercase font-mono">
          BM25 · Vector · RRF · Cross-encoder · SSE Streaming · Langfuse · Redis Cache
        </div>
      </div>
    </section>
  );
};

// --- PricingOverlay ---
const PLANS = [
  {
    name: 'Explorateur',
    price: '0',
    period: 'Gratuit pour toujours',
    desc: 'Pour découvrir DocOracle et tester le potentiel du RAG sur vos documents.',
    cta: 'Commencer gratuitement',
    highlight: false,
    features: [
      { label: 'Requêtes / jour', value: '10' },
      { label: 'Sources de lore', value: '1' },
      { label: 'Recherche BM25 standard', value: true },
      { label: 'Streaming SSE', value: true },
      { label: 'Recherche hybride Vector + BM25', value: false },
      { label: 'Re-ranking cross-encoder', value: false },
      { label: 'Synthèse vocale (TTS)', value: false },
      { label: 'Historique des sessions', value: false },
      { label: 'API REST', value: false },
      { label: 'Connecteurs MCP', value: false },
      { label: 'Support', value: 'Communauté' },
    ],
  },
  {
    name: 'Gardien',
    price: '12',
    period: '/ mois, facturé annuellement',
    desc: 'Pour les créateurs sérieux. Toute la puissance du RAG hybride sur vos archives.',
    cta: 'Essayer 14 jours gratuit',
    highlight: true,
    badge: 'Populaire',
    features: [
      { label: 'Requêtes / jour', value: '500' },
      { label: 'Sources de lore', value: '20' },
      { label: 'Recherche BM25 standard', value: true },
      { label: 'Streaming SSE', value: true },
      { label: 'Recherche hybride Vector + BM25', value: true },
      { label: 'Re-ranking cross-encoder', value: true },
      { label: 'Synthèse vocale (TTS)', value: true },
      { label: 'Historique des sessions', value: '30 jours' },
      { label: 'API REST', value: false },
      { label: 'Connecteurs MCP', value: false },
      { label: 'Support', value: 'Email prioritaire' },
    ],
  },
  {
    name: 'Oracle',
    price: '39',
    period: '/ mois, facturé annuellement',
    desc: 'Pour les studios et développeurs. Accès complet, API, MCP et support dédié.',
    cta: 'Contacter l\'équipe',
    highlight: false,
    features: [
      { label: 'Requêtes / jour', value: 'Illimitées' },
      { label: 'Sources de lore', value: 'Illimitées' },
      { label: 'Recherche BM25 standard', value: true },
      { label: 'Streaming SSE', value: true },
      { label: 'Recherche hybride Vector + BM25', value: true },
      { label: 'Re-ranking cross-encoder', value: true },
      { label: 'Synthèse vocale (TTS)', value: true },
      { label: 'Historique des sessions', value: 'Illimité' },
      { label: 'API REST', value: true },
      { label: 'Connecteurs MCP', value: true },
      { label: 'Support', value: 'Dédié + SLA 99.9%' },
    ],
  },
];

const FeatureRow = ({ label, value, highlighted }) => {
  const isTrue = value === true;
  const isFalse = value === false;
  return (
    <div className={`flex items-center justify-between py-3 border-b text-[12px] ${highlighted ? 'border-white/[0.06]' : 'border-white/[0.04]'}`}>
      <span className="text-white/45">{label}</span>
      <span className="font-medium">
        {isTrue ? <Check className="w-4 h-4 text-[#F59E0B]" /> :
          isFalse ? <span className="text-white/15">—</span> :
            <span className="text-white/70">{value}</span>}
      </span>
    </div>
  );
};

const PricingSection = ({ sectionRef }) => {
  const navigate = useNavigate();

  const plans = [
    {
      name: 'Explorateur',
      price: '0',
      period: 'Gratuit pour toujours',
      desc: 'Découvrir DocOracle et tester la recherche RAG sur un petit volume de questions.',
    },
    {
      name: 'Gardien',
      price: '12',
      period: '/ mois, facturé annuellement',
      desc: 'Le plan équilibré pour les créateurs qui veulent plus de volume et de précision.',
      badge: 'Populaire',
      highlight: true,
    },
    {
      name: 'Oracle',
      price: '39',
      period: '/ mois, facturé annuellement',
      desc: 'Accès complet pour les studios, l’API, les connecteurs et le support dédié.',
    },
  ];

  const rows = [
    { label: 'Requêtes / jour', values: ['10', '500', 'Illimitées'] },
    { label: 'Sources de lore', values: ['1', '20', 'Illimitées'] },
    { label: 'Recherche hybride', values: ['Non', 'Oui', 'Oui'] },
    { label: 'Reranking', values: ['Non', 'Oui', 'Oui'] },
    { label: 'Support', values: ['Communauté', 'Email prioritaire', 'Dédié + SLA 99.9%'] },
  ];

  return (
    <section ref={sectionRef} id="pricing" className="relative z-10 max-w-7xl mx-auto px-6 pt-28 pb-20 scroll-mt-28">
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full border border-white/[0.07]" style={{ background: 'rgba(245,158,11,0.04)' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] inline-block" />
          <span className="text-[9px] uppercase tracking-[0.3em] text-[#F59E0B]/70">Abonnements</span>
        </div>
        <h2 className="text-4xl md:text-6xl font-serif-custom tracking-tighter text-white mb-4">
          Un seul écran, trois plans.
        </h2>
        <p className="text-white/35 text-sm md:text-base max-w-2xl mx-auto leading-relaxed">
          J’ai raccourci cette section pour qu’elle reste lisible dans une seule page, sans faux scroll interne. Tu gardes l’essentiel: le prix, les écarts et les limites.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        {plans.map((plan) => (
          <div
            key={plan.name}
            className="relative rounded-[28px] border p-6 overflow-hidden"
            style={{
              background: plan.highlight ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.02)',
              borderColor: plan.highlight ? 'rgba(245,158,11,0.25)' : 'rgba(255,255,255,0.06)',
              boxShadow: plan.highlight ? '0 0 50px rgba(245,158,11,0.06)' : 'none',
            }}
          >
            {plan.highlight && (
              <div className="absolute top-0 left-0 right-0 h-px" style={{ background: 'linear-gradient(to right, transparent, #F59E0B, transparent)' }} />
            )}
            <div className="flex items-start justify-between gap-3 mb-4">
              <div>
                <h3 className="text-xl font-serif-custom italic text-white mb-1">{plan.name}</h3>
                <p className="text-[11px] text-white/30 leading-relaxed max-w-[190px]">{plan.desc}</p>
              </div>
              {plan.badge && (
                <span className="px-2.5 py-1 rounded-full text-[9px] font-bold uppercase tracking-wider text-black bg-[#F59E0B] shrink-0">
                  {plan.badge}
                </span>
              )}
            </div>

            <div className="mb-5">
              <div className="flex items-baseline gap-1">
                {plan.price === '0' ? (
                  <span className="text-4xl font-bold text-white">Gratuit</span>
                ) : (
                  <>
                    <span className="text-4xl font-bold text-white">{plan.price}€</span>
                    <span className="text-[10px] text-white/25 ml-1">/ mois</span>
                  </>
                )}
              </div>
              <div className="text-[10px] text-white/20 mt-1">{plan.period}</div>
            </div>

            <button
              onClick={() => navigate('/chat')}
              className="w-full py-3 rounded-full text-[11px] font-bold uppercase tracking-widest transition-all active:scale-95"
              style={plan.highlight
                ? { background: '#F59E0B', color: '#000' }
                : { background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.72)', border: '1px solid rgba(255,255,255,0.08)' }
              }
            >
              {plan.name === 'Oracle' ? 'Contacter l’équipe' : plan.name === 'Gardien' ? 'Essayer 14 jours gratuit' : 'Commencer gratuitement'}
            </button>
          </div>
        ))}
      </div>

      <div className="rounded-[28px] border border-white/[0.06] overflow-hidden" style={{ background: 'rgba(255,255,255,0.015)' }}>
        <div className="grid grid-cols-[1.3fr_repeat(3,1fr)] px-6 py-4 border-b border-white/[0.05] text-[10px] uppercase tracking-[0.25em] text-white/30">
          <div>Comparatif clé</div>
          <div className="text-center">Explorateur</div>
          <div className="text-center">Gardien</div>
          <div className="text-center">Oracle</div>
        </div>
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[1.3fr_repeat(3,1fr)] px-6 py-4 border-b border-white/[0.04] last:border-b-0 text-[12px]">
            <div className="text-white/45">{row.label}</div>
            <div className="text-center text-white/75">{row.values[0]}</div>
            <div className="text-center text-white/75">{row.values[1]}</div>
            <div className="text-center text-white/75">{row.values[2]}</div>
          </div>
        ))}
      </div>

      <p className="text-center text-[10px] text-white/15 mt-8 uppercase tracking-widest">
        Tous les prix HT · Résiliable à tout moment · Données hébergées en Europe
      </p>
    </section>
  );
};

const COMPACT_PLANS = [
  {
    name: 'Explorateur',
    price: '0',
    label: 'Gratuit pour toujours',
    cta: 'Commencer',
    highlight: false,
    perks: ['10 requêtes / jour', '1 source de lore', 'Recherche BM25', 'Streaming SSE'],
  },
  {
    name: 'Gardien',
    price: '12',
    label: '/ mois, facturé annuellement',
    cta: '14 jours gratuit',
    highlight: true,
    badge: 'Populaire',
    perks: ['500 requêtes / jour', '20 sources de lore', 'Hybride + Re-ranking', 'TTS · Historique 30j'],
  },
  {
    name: 'Oracle',
    price: '39',
    label: '/ mois, facturé annuellement',
    cta: "Contacter l'équipe",
    highlight: false,
    perks: ['Requêtes illimitées', 'Sources illimitées', 'API REST + MCP', 'Support dédié · SLA 99.9%'],
  },
];

const PRICING_ROWS = [
  { label: 'Requêtes / jour',         values: ['10',           '500',                  'Illimitées'] },
  { label: 'Sources de lore',          values: ['1',            '20',                   'Illimitées'] },
  { label: 'Recherche hybride',        values: [false,          true,                   true] },
  { label: 'Re-ranking cross-encoder', values: [false,          true,                   true] },
  { label: 'Synthèse vocale (TTS)',    values: [false,          true,                   true] },
  { label: 'Historique sessions',      values: [false,          '30 jours',             'Illimité'] },
  { label: 'API REST',                 values: [false,          false,                  true] },
  { label: 'Connecteurs MCP',          values: [false,          false,                  true] },
  { label: 'Support',                  values: ['Communauté',   'Email prioritaire',    'Dédié + SLA 99.9%'] },
];

const PRICING_PLANS = [
  { name: 'Curieux',  price: '0',  label: 'Gratuit pour toujours', cta: 'Commencer gratuitement', highlight: false },
  { name: 'Érudit',   price: '24', label: '/ mois, facturé annuellement', cta: '14 jours gratuit', highlight: true, badge: 'Populaire' },
  { name: 'Studio',   price: '89', label: '/ mois, facturé annuellement', cta: "Contacter l'équipe", highlight: false },
];

const PricingOverlay = ({ isOpen, onClose, navbarProps }) => {
  const navigate = useNavigate();
  const handleCta = (plan) => {
    if (plan.name === 'Studio') return; // contact link — do nothing for now
    onClose();
    navigate('/chat');
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[600] overflow-hidden">
          {/* Video background */}
          <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
            <video
              className="absolute inset-0 w-full h-full object-cover"
              style={{ filter: 'blur(18px)', transform: 'scale(1.08)' }}
              src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4"
              muted autoPlay loop playsInline />
            <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.72)' }} />
          </div>

          <div className="absolute inset-0 z-10 flex flex-col overflow-y-auto">
            {navbarProps && <Navbar {...navbarProps} />}

            <div className="flex-1 flex items-start justify-center px-4 py-10 pt-28">
              <div className="w-full max-w-5xl">

                {/* Header */}
                <div className="text-center mb-10">
                  <div className="inline-flex items-center gap-2 mb-4 px-4 py-1.5 rounded-full border border-white/[0.07]" style={{ background: 'rgba(245,158,11,0.04)' }}>
                    <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] inline-block" />
                    <span className="text-[9px] uppercase tracking-[0.3em] text-[#F59E0B]/70 font-mono">Abonnements</span>
                  </div>
                  <h2 className="text-4xl md:text-5xl font-serif-custom tracking-tighter text-white mb-2">
                    Le bon plan,<em className="italic text-white/40"> au bon moment.</em>
                  </h2>
                  <p className="text-white/30 text-sm">Sans engagement. Résiliable à tout moment. Données hébergées en Europe.</p>
                </div>

                {/* Plan header cards */}
                <div className="grid grid-cols-3 gap-3 mb-0">
                  {PRICING_PLANS.map((plan, i) => (
                    <motion.div
                      key={plan.name}
                      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.08 + i * 0.07, ease: [0.22, 1, 0.36, 1] }}
                      className="relative rounded-t-[20px] rounded-b-none p-5 pb-4"
                      style={{
                        background: plan.highlight ? 'rgba(245,158,11,0.07)' : 'rgba(255,255,255,0.025)',
                        border: plan.highlight ? '1px solid rgba(245,158,11,0.28)' : '1px solid rgba(255,255,255,0.07)',
                        borderBottom: 'none',
                      }}
                    >
                      {plan.highlight && (
                        <div className="absolute top-0 left-0 right-0 h-px rounded-t-[20px]"
                          style={{ background: 'linear-gradient(to right, transparent, #F59E0B, transparent)' }} />
                      )}
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-base font-serif-custom italic text-white">{plan.name}</h3>
                        {plan.badge && (
                          <span className="px-2 py-0.5 rounded-full text-[8px] font-bold uppercase tracking-wider text-black bg-[#F59E0B]">{plan.badge}</span>
                        )}
                      </div>
                      <div className="flex items-baseline gap-1 mb-0.5">
                        {plan.price === '0' ? (
                          <span className="text-2xl font-bold text-white">Gratuit</span>
                        ) : (
                          <>
                            <span className="text-2xl font-bold text-white">{plan.price}€</span>
                            <span className="text-[9px] text-white/25">/ mois</span>
                          </>
                        )}
                      </div>
                      <div className="text-[9px] text-white/20">{plan.label}</div>
                    </motion.div>
                  ))}
                </div>

                {/* Feature comparison table */}
                <div className="rounded-b-[20px] border border-white/[0.06] overflow-hidden mb-4" style={{ background: 'rgba(255,255,255,0.015)' }}>
                  {PRICING_ROWS.map((row, ri) => (
                    <div
                      key={row.label}
                      className="grid grid-cols-[1.6fr_1fr_1fr_1fr] text-[11px] border-b border-white/[0.04] last:border-b-0"
                      style={{ background: ri % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.012)' }}
                    >
                      <div className="px-5 py-3 text-white/40">{row.label}</div>
                      {row.values.map((val, vi) => (
                        <div key={vi} className="px-3 py-3 flex items-center justify-center">
                          {val === true  ? <Check size={13} className="text-[#F59E0B]" /> :
                           val === false ? <span className="text-white/15 text-base leading-none">—</span> :
                           <span className="text-white/60 text-center">{val}</span>}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>

                {/* CTA row */}
                <div className="grid grid-cols-3 gap-3">
                  {PRICING_PLANS.map((plan) => (
                    <button
                      key={plan.name}
                      onClick={() => handleCta(plan)}
                      className="w-full py-3 rounded-full text-[10px] font-bold uppercase tracking-widest transition-all active:scale-95 hover:scale-[1.02]"
                      style={plan.highlight
                        ? { background: '#F59E0B', color: '#000' }
                        : { background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.65)', border: '1px solid rgba(255,255,255,0.09)' }
                      }
                    >
                      {plan.cta}
                    </button>
                  ))}
                </div>

                <p className="text-center text-[9px] text-white/15 mt-6 uppercase tracking-widest">
                  Tous les prix HT · Résiliable à tout moment · Données hébergées en Europe
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// --- ArchitecturePage ---

const FadeInSection = ({ children, className = "" }) => (
  <div className={className}>{children}</div>
);

const PipelineStep = ({ icon: Icon, step, title, desc, color = "#F59E0B", delay = 0 }) => (
  <div className="flex gap-5 items-start group">
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
  </div>
);

const CompareCard = ({ title, items, accent, icon: Icon }) => (
  <div
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
  </div>
);

const StatPill = ({ value, label }) => (
  <div className="liquid-glass border border-white/[0.07] rounded-[24px] px-8 py-6 text-center">
    <div className="text-3xl font-bold text-[#F59E0B] mb-1">{value}</div>
    <div className="text-[11px] uppercase tracking-widest text-white/30">{label}</div>
  </div>
);

const TechCard = ({ tech }) => (
  <div className="liquid-glass border border-white/[0.06] rounded-[20px] p-5 group hover:border-white/10 transition-all">
    <div className="text-[9px] uppercase tracking-[0.25em] mb-2" style={{ color: `${tech.color}70` }}>{tech.label}</div>
    <div className="text-[15px] font-semibold text-white/80 group-hover:text-white transition-colors">{tech.value}</div>
    <div className="mt-3 h-[2px] w-8 rounded-full transition-all duration-300 group-hover:w-full" style={{ background: `linear-gradient(to right, ${tech.color}60, transparent)` }} />
  </div>
);

const ArchitecturePage = () => {

  const pipeline = [
    {
      icon: MessageSquare,
      title: "Entrée utilisateur",
      desc: "La question arrive depuis l'UI, avec le contexte de session, l'utilisateur authentifié, et les métadonnées de conversation utiles au traitement.",
      color: "#F59E0B",
    },
    {
      icon: Shield,
      title: "Filtrage & normalisation",
      desc: "On nettoie la requête, on retire les artefacts inutiles, on masque les données sensibles si nécessaire et on prépare un prompt sûr pour la suite du pipeline.",
      color: "#60a5fa",
    },
    {
      icon: Brain,
      title: "Reformulation contextuelle",
      desc: "Si la question contient des anaphores (\"il\", \"elle\", \"ça\"…), un modèle Groq léger la reformule en s'appuyant sur l'historique des derniers échanges.",
      color: "#a78bfa",
    },
    {
      icon: Search,
      title: "Recherche hybride",
      desc: "La question est envoyée à deux moteurs en parallèle : BM25 pour les correspondances exactes et Qdrant pour la similarité sémantique.",
      color: "#f87171",
    },
    {
      icon: GitBranch,
      title: "Fusion RRF",
      desc: "Les résultats des deux moteurs sont fusionnés avec Reciprocal Rank Fusion pour garder les passages les plus utiles sans surpondérer un seul moteur.",
      color: "#fbbf24",
    },
    {
      icon: Layers,
      title: "Re-ranking intelligent",
      desc: "Un cross-encoder réordonne les passages retenus et saute l'étape si le top-1 est déjà suffisamment confiant pour gagner du temps.",
      color: "#c084fc",
    },
    {
      icon: Check,
      title: "Sécurité & ancrage",
      desc: "Chaque lot de passages et chaque réponse candidate passent par le juge LLM et les filtres anti-PII pour éviter les hallucinations et les fuites de données.",
      color: "#f87171",
    },
    {
      icon: Zap,
      title: "Génération streaming",
      desc: "Le LLM principal via OpenRouter streame sa réponse token par token. En cas d'erreur, la chaîne bascule automatiquement sur les fallbacks configurés.",
      color: "#fbbf24",
    },
    {
      icon: BarChart3,
      title: "Observabilité & mémoire",
      desc: "La requête, les latences, les scores et les feedbacks sont tracés dans Langfuse, puis résumés pour alimenter la mémoire long-terme utilisateur.",
      color: "#34d399",
    },
  ];

  const pipelineFlow = [
    'UI',
    'Auth',
    'Sanitize',
    'Rewrite',
    'BM25',
    'Vector',
    'RRF',
    'Rerank',
    'Judge',
    'LLM',
    'Feedback',
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
        "Contexte universel — ne connaît pas votre documentation interne.",
        "Impossible d'ajouter de nouvelles données sans re-entraîner.",
      ],
    },
    {
      title: "DocOracle RAG",
      accent: "#F59E0B",
      icon: Database,
      items: [
        "Répond uniquement depuis vos documents indexés — jamais en dehors.",
        "Chaque affirmation est ancrée dans un passage source citable.",
        "Recherche hybride (vecteurs + BM25) pour ne rater aucune correspondance.",
        "Mémoire long-terme par utilisateur — le contexte s'enrichit à chaque session.",
        "Ajout de documents en temps réel via l'ingestion — sans toucher au modèle.",
      ],
    },
  ];

  const techStack = [
    { label: "Vector DB", value: "Qdrant", color: "#F59E0B" },
    { label: "Search", value: "BM25 + RRF", color: "#60a5fa" },
    { label: "LLM", value: "OpenRouter / Groq", color: "#a78bfa" },
    { label: "Reranker", value: "Cross-encoder", color: "#fbbf24" },
    { label: "Tracing", value: "Langfuse", color: "#f87171" },
    { label: "Auth", value: "Supabase", color: "#34d399" },
    { label: "Protocol", value: "MCP (stdio/SSE)", color: "#fb923c" },
    { label: "Cache", value: "Redis Semantic", color: "#e879f9" },
  ];

  return (
    <div className="relative min-h-screen text-white">
      {/* Video background — désactivée (garder pour réactiver) */}
      {/* <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <video className="absolute inset-0 w-full h-full object-cover opacity-20 mix-blend-screen"
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260314_131748_f2ca2a28-fed7-44c8-b9a9-bd9acdd5ec31.mp4"
          muted autoPlay loop playsInline />
        <div className="absolute inset-0 bg-gradient-to-b from-black/75 via-black/55 to-black/85" />
      </div> */}

      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-40 pb-32">

        {/* Hero */}
        <FadeInSection className="mb-24 text-center">
          <div className="inline-flex items-center gap-2 liquid-glass border border-white/[0.07] rounded-full px-5 py-2 mb-8">
            <GitBranch size={12} className="text-[#F59E0B]" />
            <span className="text-[10px] uppercase tracking-[0.3em] text-white/40">Architecture Technique</span>
          </div>
          <h1 className="text-6xl md:text-8xl font-serif-custom tracking-tighter leading-[0.88] text-white mb-8">
            Pas une IA.<br />
            <em className="italic text-white/40">Un oracle.</em>
          </h1>
          <p className="text-white/40 text-lg max-w-2xl mx-auto leading-relaxed font-light">
            DocOracle ne devine pas. Il consulte. Chaque réponse est construite depuis vos documents réels,
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
            <div className="text-[10px] uppercase tracking-[0.3em] text-[#F59E0B]/60 mb-3">Pipeline RAG</div>
            <h2 className="text-4xl md:text-5xl font-serif-custom tracking-tighter text-white">Comment ça fonctionne</h2>
            <p className="mt-4 max-w-3xl text-white/35 text-sm md:text-base leading-relaxed">
              Voici la chaîne complète, de la requête utilisateur jusqu'à l'indexation des signaux de feedback et de mémoire.
              Chaque étape est pensée pour limiter les erreurs, améliorer la pertinence et garder un système observable.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-6">
            {pipelineFlow.map((node, index) => (
              <div key={node} className="flex items-center gap-2">
                <span className="px-3 py-1.5 rounded-full border border-white/[0.08] text-[10px] uppercase tracking-[0.25em] text-white/55 bg-white/[0.02]">
                  {node}
                </span>
                {index < pipelineFlow.length - 1 && <span className="text-white/15 text-xs">→</span>}
              </div>
            ))}
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
              style={{ background: "radial-gradient(ellipse at 50% 0%, rgba(245,158,11,0.06) 0%, transparent 60%)" }}
            />
            <h2 className="text-4xl md:text-6xl font-serif-custom tracking-tighter text-white mb-5 relative z-10">
              Prêt à interroger l'Oracle ?
            </h2>
            <p className="text-white/35 mb-10 max-w-lg mx-auto text-[15px] leading-relaxed relative z-10">
              Indexez votre documentation. Posez vos questions en langage naturel. DocOracle consulte vos sources, cite ses références, et ne s'invente jamais de réponse.
            </p>
            <button
              onClick={() => navigate('/chat')}
              className="relative z-10 group inline-flex items-center gap-3 liquid-glass bg-white/5 border border-white/10 text-white font-bold px-10 py-5 rounded-full text-sm uppercase tracking-widest hover:bg-white/10 hover:border-white/20 hover:scale-105 active:scale-95 transition-all shadow-2xl"
            >
              <Sparkles className="w-4 h-4 text-[#F59E0B] group-hover:rotate-12 transition-transform" />
              Essayer DocOracle
              <ArrowUpRight className="w-4 h-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            </button>
          </div>
        </FadeInSection>
      </div>
    </div>
  );
};

// --- LegalModal ---
const LEGAL_CONTENT = {
  privacy: {
    title: 'Politique de confidentialité',
    updated: 'Avril 2026',
    sections: [
      { heading: 'Données collectées', body: 'Nous collectons votre adresse email lors de la création de compte via Supabase Auth. Les messages envoyés au chatbot sont stockés en base de données pour maintenir l\'historique de session. Les votes de feedback (👍/👎) sont transmis à Langfuse pour l\'observabilité RAG.' },
      { heading: 'Utilisation des données', body: 'Vos données sont utilisées exclusivement pour faire fonctionner le service DocOracle. Elles ne sont jamais vendues, revendues ni partagées avec des tiers à des fins commerciales. Les appels LLM transitent par OpenRouter et Groq — chaque fournisseur est soumis à sa propre politique de rétention (0–30 jours).' },
      { heading: 'Hébergement & sécurité', body: 'Toutes les données utilisateurs sont hébergées en Europe (Supabase EU West — région Frankfurt). Les vecteurs d\'embedding sont stockés dans Qdrant Cloud EU. Les connexions sont chiffrées TLS 1.3. Les mots de passe ne transitent jamais en clair.' },
      { heading: 'Cookies & stockage local', body: 'Nous n\'utilisons pas de cookies tiers ou publicitaires. Un token de session est stocké dans localStorage pour maintenir votre connexion. Ce token est supprimé à la déconnexion. Le mode invité utilise un identifiant anonyme local (oracleGuestId).' },
      { heading: 'Vos droits', body: 'Conformément au RGPD, vous disposez d\'un droit d\'accès, de rectification, de portabilité et de suppression de vos données. Pour exercer ces droits, ouvrez une issue sur le dépôt GitHub du projet. Nous traitons les demandes sous 30 jours.' },
    ],
  },
  terms: {
    title: 'Conditions d\'utilisation',
    updated: 'Avril 2026',
    sections: [
      { heading: 'Objet du service', body: 'DocOracle est un système RAG (Retrieval-Augmented Generation) destiné à l\'interrogation de documentation interne, bases de connaissance et corpus textuels. Le service est opéré dans le cadre d\'un projet en production.' },
      { heading: 'Usage autorisé', body: 'Le service est réservé à un usage personnel, professionnel et éducatif. Toute utilisation abusive ou détournée est interdite. Vous vous engagez à ne soumettre que des contenus dont vous possédez les droits d\'utilisation.' },
      { heading: 'Usages interdits', body: 'Sont strictement interdits : les tentatives d\'injection de prompt, de jailbreak ou de contournement des mesures de sécurité ; la génération de contenus illégaux, diffamatoires ou malveillants ; le scraping automatisé ou les requêtes massives dépassant les limites du plan ; toute activité visant à nuire au service ou à ses utilisateurs.' },
      { heading: 'Limitation de responsabilité', body: 'DocOracle est fourni "tel quel", sans garantie de disponibilité continue ni d\'exactitude des réponses générées. Les réponses du système sont générées par des LLM et peuvent contenir des inexactitudes. Elles ne constituent en aucun cas un avis juridique, médical ou professionnel.' },
      { heading: 'Résiliation', body: 'DocOracle se réserve le droit de suspendre ou supprimer tout compte en cas d\'abus, de violation des présentes conditions ou de comportement nuisible, sans préavis. Les utilisateurs peuvent demander la suppression de leur compte à tout moment.' },
    ],
  },
};

const LegalModal = ({ type, onClose }) => {
  const data = LEGAL_CONTENT[type];
  if (!data) return null;
  return (
    <div className="fixed inset-0 z-[800] flex items-center justify-center p-6">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="absolute inset-0 bg-black/85 backdrop-blur-md" />
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 280, damping: 26 }}
        className="relative z-10 w-full max-w-2xl max-h-[82vh] flex flex-col rounded-[28px] border border-white/[0.07] overflow-hidden"
        style={{ background: '#090909' }}
      >
        <div className="flex items-center justify-between px-8 py-6 border-b border-white/[0.05] shrink-0">
          <h2 className="text-xl font-serif-custom tracking-tighter text-white">{data.title}</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center text-white/40 hover:text-white hover:border-white/25 transition-all">
            <X size={13} />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-8 py-8 space-y-8" style={{ scrollbarWidth: 'none' }}>
          {data.sections.map(s => (
            <div key={s.heading}>
              <div className="text-[9px] uppercase tracking-[0.3em] text-[#F59E0B]/55 mb-2">{s.heading}</div>
              <p className="text-[12px] text-white/45 leading-relaxed">{s.body}</p>
            </div>
          ))}
          <div className="pt-6 border-t border-white/[0.05] text-[9px] text-white/20 uppercase tracking-widest">
            DocOracle · Dernière mise à jour : {data.updated}
          </div>
        </div>
      </motion.div>
    </div>
  );
};

// --- RagSection ---
const RAG_CARDS = [
  {
    icon: Search,
    color: '#60a5fa',
    title: 'BM25',
    subtitle: 'Recherche lexicale',
    desc: 'Correspondance exacte sur vos textes. Rapide et précis sur les termes métier, les noms propres et les références techniques.',
  },
  {
    icon: Database,
    color: '#F59E0B',
    title: 'Vector Search',
    subtitle: 'Qdrant — similarité sémantique',
    desc: 'Trouve les passages conceptuellement proches, même si aucun mot ne correspond exactement à la requête.',
  },
  {
    icon: GitBranch,
    color: '#fbbf24',
    title: 'RRF Fusion',
    subtitle: 'Reciprocal Rank Fusion',
    desc: 'Fusionne les classements BM25 et vecteur en un score équilibré — le meilleur des deux moteurs en un seul résultat.',
  },
  {
    icon: Layers,
    color: '#c084fc',
    title: 'Re-ranking',
    subtitle: 'Cross-encoder',
    desc: 'Un second modèle réordonne les passages retenus par pertinence maximale avant de les soumettre au LLM.',
  },
  {
    icon: Zap,
    color: '#34d399',
    title: 'LLM Streaming',
    subtitle: 'OpenRouter · SSE',
    desc: 'La réponse arrive token par token avec basculement automatique sur 4 modèles de fallback en cas d\'erreur.',
  },
  {
    icon: BarChart3,
    color: '#f87171',
    title: 'Observabilité',
    subtitle: 'Langfuse · Traces complètes',
    desc: 'Chaque requête est tracée — latences, scores de pertinence, feedback utilisateur — pour améliorer le pipeline.',
  },
];

const RagSection = () => (
  <section className="relative py-28 px-6 md:px-12">
    <div className="max-w-7xl mx-auto">
      <div className="text-center mb-16">
        <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full border border-white/[0.07]" style={{ background: 'rgba(245,158,11,0.04)' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] inline-block" />
          <span className="text-[9px] uppercase tracking-[0.3em] text-[#F59E0B]/70 font-mono">Comment ça fonctionne</span>
        </div>
        <h2 className="text-4xl md:text-6xl font-serif-custom tracking-tighter text-white mb-5">
          Pas de magie.<br /><em className="italic text-white/35">De la méthode.</em>
        </h2>
        <p className="text-white/30 text-sm md:text-base max-w-xl mx-auto leading-relaxed">
          Chaque composant remplit un rôle précis. Ensemble, ils forment un système qui ne devine pas — il consulte vos documents, vérifie, et cite.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {RAG_CARDS.map((card, i) => (
          <motion.div
            key={card.title}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: i * 0.08, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="liquid-glass rounded-[28px] border border-white/[0.06] p-7 group hover:border-white/10 transition-all"
          >
            <div className="w-10 h-10 rounded-2xl flex items-center justify-center mb-5" style={{ background: `${card.color}18` }}>
              <card.icon size={18} style={{ color: card.color }} />
            </div>
            <div className="text-[9px] uppercase tracking-[0.3em] mb-1.5" style={{ color: `${card.color}80` }}>{card.subtitle}</div>
            <h3 className="text-lg font-semibold text-white mb-2">{card.title}</h3>
            <p className="text-[12px] text-white/40 leading-relaxed">{card.desc}</p>
          </motion.div>
        ))}
      </div>
    </div>
  </section>
);

// --- Footer ---
const Footer = () => {
  const [legal, setLegal] = useState(null); // null | 'privacy' | 'terms'
  return (
    <footer className="bg-black pt-20 pb-12 px-10 border-t border-white/5 relative z-10">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-end gap-12">
        <div>
          <h2 className="text-7xl md:text-9xl font-serif-custom text-white tracking-tighter mb-6">DocOracle</h2>
          <p className="text-white/20 tracking-[0.4em] uppercase text-[10px]">Your documents. Instant answers. Zero hallucination.</p>
        </div>
        <div className="text-right">
          <p className="text-white/40 mb-8 max-w-xs ml-auto text-sm italic">"Not a chatbot. A retrieval engine. Every answer sourced, never invented."</p>
        </div>
      </div>
      <div className="max-w-7xl mx-auto mt-20 pt-12 border-t border-white/5 flex flex-col md:flex-row justify-between text-[10px] uppercase tracking-[0.4em] text-white/20 gap-4">
        <span>© 2026 DocOracle</span>
        <div className="flex gap-8">
          <button onClick={() => setLegal('privacy')} className="hover:text-white transition-colors cursor-pointer">Privacy</button>
          <button onClick={() => setLegal('terms')} className="hover:text-white transition-colors cursor-pointer">Terms</button>
          <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">GitHub</a>
        </div>
      </div>
      <AnimatePresence>
        {legal && <LegalModal type={legal} onClose={() => setLegal(null)} />}
      </AnimatePresence>
    </footer>
  );
};

// --- App ---
export default function App() {
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [isPricingOpen, setIsPricingOpen] = useState(false);
  const [isDocsOpen, setIsDocsOpen] = useState(false);
  const [isArchitectureOpen, setIsArchitectureOpen] = useState(false);
  const [user, setUser] = useState(null); // { email, isGuest } | null
  const location = useLocation();
  const navigate = useNavigate();

  // ── Callbacks définis AVANT les useEffect qui en dépendent ──────────────
  const closeAll = useCallback(() => {
    setIsPricingOpen(false);
    setIsLoginOpen(false);
    setIsDocsOpen(false);
    setIsArchitectureOpen(false);
  }, []);

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

  useEffect(() => {
    closeAll();
  }, [location.pathname, closeAll]);

  // Ouvrir le login modal si on arrive depuis une redirection /chat
  useEffect(() => {
    if (location.state?.openLogin) {
      setIsLoginOpen(true);
    }
  }, [location.state]);

  const handleNavigate = useCallback((path) => {
    closeAll();
    navigate(path, { state: {} });
    if (path === '/') {
      requestAnimationFrame(() => {
        if (window.__lenis) {
          window.__lenis.scrollTo(0, { immediate: false, duration: 0.8 });
        } else {
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      });
    }
  }, [closeAll, navigate]);

  const openPricing = useCallback(() => {
    closeAll();
    setIsPricingOpen(true);
  }, [closeAll]);

  const openLogin = useCallback(() => {
    setIsPricingOpen(false); setIsDocsOpen(false); setIsArchitectureOpen(false);
    setIsLoginOpen(true);
  }, []);

  const openDocs = useCallback(() => {
    setIsPricingOpen(false); setIsLoginOpen(false); setIsArchitectureOpen(false);
    setIsDocsOpen(true);
  }, []);

  const openArchitecture = useCallback(() => {
    setIsPricingOpen(false); setIsLoginOpen(false); setIsDocsOpen(false);
    setIsArchitectureOpen(true);
  }, []);

  // Pause Lenis + bloque scroll natif quand un overlay est ouvert
  // Lenis intercepte les événements wheel directement → overflow:hidden seul ne suffit pas
  useEffect(() => {
    const anyOverlay = isDocsOpen || isArchitectureOpen || isPricingOpen;
    if (anyOverlay) {
      window.__lenis?.stop();
      document.body.style.overflow = 'hidden';
      document.documentElement.style.overflow = 'hidden';
    } else {
      window.__lenis?.start();
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
    }
    return () => {
      window.__lenis?.start();
      document.body.style.overflow = '';
      document.documentElement.style.overflow = '';
    };
  }, [isDocsOpen, isArchitectureOpen, isPricingOpen]);

  return (
    <>
      <LenisReset />
      <CursorGlow />
      <Routes>
        {/* ── Panel Monitoring ─────────────────────────────── */}
        <Route path="/monitoring" element={<MonitoringRoute />} />

        {/* ── Page Chat ────────────────────────────────────── */}
        <Route path="/chat" element={
          <ChatRoute user={user} onLogout={handleLogout} onLoginOpen={() => setIsLoginOpen(true)} />
        } />

        {/* ── Landing (toutes les autres routes) ───────────── */}
        <Route path="*" element={
          <div className="relative bg-black" style={{ WebkitUserSelect: 'none' }}>
            <style dangerouslySetInnerHTML={{ __html: styles }} />

            {/* Blurred dezoom video bg — désactivée (garder pour réactiver) */}
            {/* <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
            <video
              className="absolute inset-0 w-full h-full object-cover opacity-15 mix-blend-screen"
              style={{ transform: 'scale(0.85)', filter: 'blur(32px)' }}
              src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4"
              muted autoPlay loop playsInline
            />
            <div className="absolute inset-0 bg-black/50" />
          </div> */}

            <div className="grid-line" style={{ left: '25%' }} />
            <div className="grid-line" style={{ left: '50%' }} />
            <div className="grid-line" style={{ left: '75%' }} />

            <Navbar
              onLoginClick={openLogin}
              onPricingClick={openPricing}
              onDocsClick={openDocs}
              onArchitectureClick={openArchitecture}
              onNavigate={handleNavigate}
              user={user}
              onLogout={handleLogout}
            />
            <HeroSection />
            <PinnedReveal />
            <RagSection />
            <Footer />

            <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} onAuthSuccess={handleAuthSuccess} />

            <PricingOverlay isOpen={isPricingOpen} onClose={() => setIsPricingOpen(false)} navbarProps={{ onLoginClick: openLogin, onPricingClick: openPricing, onDocsClick: openDocs, onArchitectureClick: openArchitecture, onNavigate: handleNavigate, user, onLogout: handleLogout }} />

            {/* Docs & Architecture — overlays, pas de route → pas d'écran noir */}
            <AnimatePresence>
              {isDocsOpen && (
                <motion.div key="docs-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[600] overflow-hidden">
                  {/* Video background */}
                  <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
                    <video
                      className="absolute inset-0 w-full h-full object-cover"
                      style={{ filter: 'blur(18px)', transform: 'scale(1.08)' }}
                      src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4"
                      muted autoPlay loop playsInline />
                    <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.72)' }} />
                  </div>
                  <div
                    className="absolute inset-0 z-10 overflow-y-auto overscroll-contain"
                    onWheelCapture={(event) => event.stopPropagation()}
                    onTouchMoveCapture={(event) => event.stopPropagation()}
                  >
                  <Navbar onLoginClick={openLogin} onPricingClick={openPricing} onDocsClick={openDocs} onArchitectureClick={openArchitecture} onNavigate={handleNavigate} user={user} onLogout={handleLogout} />
                  <DocsPage />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {isArchitectureOpen && (
                <motion.div key="arch-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[600] overflow-hidden">
                  {/* Video background */}
                  <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden">
                    <video
                      className="absolute inset-0 w-full h-full object-cover"
                      style={{ filter: 'blur(18px)', transform: 'scale(1.08)' }}
                      src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260324_151826_c7218672-6e92-402c-9e45-f1e0f454bdc4.mp4"
                      muted autoPlay loop playsInline />
                    <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.72)' }} />
                  </div>
                  <div
                    className="absolute inset-0 z-10 overflow-y-auto overscroll-contain"
                    onWheelCapture={(event) => event.stopPropagation()}
                    onTouchMoveCapture={(event) => event.stopPropagation()}
                  >
                  <Navbar onLoginClick={openLogin} onPricingClick={openPricing} onDocsClick={openDocs} onArchitectureClick={openArchitecture} onNavigate={handleNavigate} user={user} onLogout={handleLogout} />
                  <ArchitecturePage />
                  <Footer />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        } />
      </Routes>
    </>
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
