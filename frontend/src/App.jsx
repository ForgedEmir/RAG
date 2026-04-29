import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { onAuthStateChange, logout } from './auth.js';
import { useGlobalLenis } from './useLenis.js';
import LoginPage from './pages/LoginPage.jsx';
import ChatPage from './pages/ChatPage.jsx';
import DocsPage from './pages/DocsPage.jsx';
import MonitoringPage from './pages/MonitoringPage.jsx';

export default function App() {
  const [user, setUser] = useState(() => {
    const id = localStorage.getItem('rabeliaGuestId') || localStorage.getItem('oracleGuestId');
    return id ? { id, isGuest: true } : null;
  });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // Guest already known from localStorage — no need to wait for Supabase
    const guestId = localStorage.getItem('rabeliaGuestId') || localStorage.getItem('oracleGuestId');
    if (guestId) setLoading(false);

    const unsub = onAuthStateChange((u) => {
      if (u !== null) {
        setUser(u);
      } else {
        // SIGNED_OUT from Supabase must not clear an active guest session
        setUser(prev => (prev?.isGuest ? prev : null));
      }
      setLoading(false);
    });
    // timeout fallback si Supabase non configuré
    const t = setTimeout(() => setLoading(false), 3000);
    return () => { unsub(); clearTimeout(t); };
  }, []);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    navigate('/login');
  };

  if (loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-app)' }}>
        <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>Chargement…</div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={
        user ? <Navigate to="/chat" replace /> : <LoginPage onLogin={setUser} />
      } />
      <Route path="/chat" element={
        user ? <ChatPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />
      } />
      <Route path="/docs" element={
        user ? <DocsPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />
      } />
      <Route path="/monitoring" element={
        <MonitoringPage user={user} onLogout={handleLogout} />
      } />
      <Route path="*" element={<Navigate to={user ? '/chat' : '/login'} replace />} />
    </Routes>
  );
}
