import { useState, useEffect, Component } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { withTranslation, useTranslation } from 'react-i18next';
import { onAuthStateChange, logout, getAuthHeader } from './auth.js';
import { useGlobalLenis } from './useLenis.js';
import LoginPage from './pages/LoginPage.jsx';
import ChatPage from './pages/ChatPage.jsx';
import DocsPage from './pages/DocsPage.jsx';
import MonitoringPage from './pages/MonitoringPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import AdminPage from './pages/AdminPage.jsx';

class ErrorBoundaryRaw extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    const { t } = this.props;
    if (this.state.error) return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, background: 'var(--bg-app)' }}>
        <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>{t('app.error_unexpected')}</div>
        <button
          onClick={() => window.location.reload()}
          style={{ padding: '8px 18px', borderRadius: 6, background: 'var(--accent)', color: '#000', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
        >
          {t('app.reload')}
        </button>
      </div>
    );
    return this.props.children;
  }
}
const ErrorBoundary = withTranslation()(ErrorBoundaryRaw);

function AuthCallback() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  useEffect(() => {
    // Supabase JS auto-detects the PKCE code in the URL and creates the session.
    // onAuthStateChange in App() will update user -> navigate to /chat.
    const tid = setTimeout(() => navigate('/login', { replace: true }), 5000);
    return () => clearTimeout(tid);
  }, [navigate]);
  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-app)' }}>
      <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>{t('app.connecting')}</div>
    </div>
  );
}

export default function App() {
  const { t } = useTranslation();
  const [user, setUser] = useState(() => {
    const id = localStorage.getItem('rabeliaGuestId') || localStorage.getItem('oracleGuestId');
    return id ? { id, isGuest: true } : null;
  });
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // Guest already known from localStorage — no need to wait for Supabase
    const guestId = localStorage.getItem('rabeliaGuestId') || localStorage.getItem('oracleGuestId');
    if (guestId) setLoading(false);

    const unsub = onAuthStateChange((u) => {
      if (u !== null) {
        setUser(u);
        // Auto-accept pending team invitations silently
        if (!u.isGuest) {
          getAuthHeader().then(headers => {
            fetch('/api/team/join', { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers } }).catch(() => {});
            fetch('/api/auth/me', { headers }).then(r => r.ok ? r.json() : null).then(d => {
              if (d?.is_admin) setIsAdmin(true);
            }).catch(() => {});
          }).catch(() => {});
        }
      } else {
        // SIGNED_OUT from Supabase must not clear an active guest session
        setUser(prev => (prev?.isGuest ? prev : null));
        setIsAdmin(false);
      }
      setLoading(false);
    });
    // timeout fallback if Supabase is not configured
    const tid = setTimeout(() => setLoading(false), 3000);
    return () => { unsub(); clearTimeout(tid); };
  }, []);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setIsAdmin(false);
    navigate('/login');
  };

  if (loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-app)' }}>
        <div style={{ fontSize: 13, color: 'var(--fg-muted)' }}>{t('app.loading')}</div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
    <Routes>
      <Route path="/login" element={
        user ? <Navigate to="/chat" replace /> : <LoginPage onLogin={setUser} />
      } />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/chat" element={
        user ? <ChatPage user={user} onLogout={handleLogout} isAdmin={isAdmin} /> : <Navigate to="/login" replace />
      } />
      <Route path="/docs" element={
        user ? <DocsPage user={user} onLogout={handleLogout} isAdmin={isAdmin} /> : <Navigate to="/login" replace />
      } />
      <Route path="/monitoring" element={
        <MonitoringPage user={user} onLogout={handleLogout} isAdmin={isAdmin} />
      } />
      <Route path="/settings" element={
        user ? <SettingsPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />
      } />
      <Route path="/admin" element={
        user ? <AdminPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />
      } />
      <Route path="*" element={<Navigate to={user ? '/chat' : '/login'} replace />} />
    </Routes>
    </ErrorBoundary>
  );
}
