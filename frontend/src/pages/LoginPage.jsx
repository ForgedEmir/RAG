import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RabeliaLogo from '../components/RabeliaLogo.jsx';
import Icon from '../components/Icon.jsx';
import { loginWithEmail, loginWithGithub, loginWithGoogle, getOrCreateGuestId } from '../auth.js';

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await loginWithEmail(email, password);
      navigate('/chat');
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSocial = async (provider) => {
    try {
      if (provider === 'github') await loginWithGithub();
      if (provider === 'google') await loginWithGoogle();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleGuest = () => {
    const guestId = getOrCreateGuestId();
    onLogin({ id: guestId, isGuest: true });
    navigate('/chat');
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-app)',
      position: 'relative',
    }}>
      <div style={{
        position: 'absolute', top: 24, left: 28,
        fontSize: 11, color: 'var(--fg-muted)',
        letterSpacing: '0.08em', textTransform: 'uppercase',
        fontFamily: 'var(--font-mono)',
      }}>
        Client Portal · v2.4
      </div>
      <div style={{
        position: 'absolute', bottom: 24, left: 28, right: 28,
        display: 'flex', justifyContent: 'space-between',
        fontSize: 11, color: 'var(--fg-muted)',
      }}>
        <span>© RABELIA 2026</span>
        <span>support@rabelia.fr</span>
      </div>

      <div style={{ width: 380, textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
          <RabeliaLogo size="lg" />
        </div>

        <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 8px', letterSpacing: '-0.015em' }}>
          Login to your workspace
        </h1>
        <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 28px', lineHeight: 1.55 }}>
          Access your document assistant.
        </p>

        {error && (
          <div style={{
            marginBottom: 16, padding: '10px 14px',
            background: 'var(--danger-soft)', border: '1px solid var(--danger)',
            borderRadius: 'var(--r-md)', fontSize: 13, color: 'var(--danger)',
            textAlign: 'left',
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ textAlign: 'left' }}>
          <div style={{ marginBottom: 12 }}>
            <label className="rb-label" htmlFor="email">Email address</label>
            <input
              id="email"
              className="rb-input rb-input--lg"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="vous@entreprise.com"
              autoComplete="email"
              required
            />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label className="rb-label" htmlFor="password">Password</label>
            <div style={{ position: 'relative' }}>
              <input
                id="password"
                className="rb-input rb-input--lg"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
                required
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                style={{
                  position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--fg-muted)', padding: 4,
                }}
              >
                <Icon name={showPassword ? 'eye_off' : 'eye'} size={16} />
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="rb-btn rb-btn--primary rb-btn--lg rb-btn--block"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div style={{ margin: '20px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
          <span style={{ fontSize: 11, color: 'var(--fg-muted)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>ou</span>
          <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
          <button
            className="rb-btn rb-btn--secondary"
            onClick={() => handleSocial('github')}
            style={{ gap: 8 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            GitHub
          </button>
          <button
            className="rb-btn rb-btn--secondary"
            onClick={() => handleSocial('google')}
            style={{ gap: 8 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Google
          </button>
        </div>

        <button
          className="rb-btn rb-btn--ghost rb-btn--block"
          onClick={handleGuest}
          style={{ marginTop: 4, fontSize: 12, color: 'var(--fg-muted)' }}
        >
          Continue without account (guest mode)
        </button>

        <p style={{ fontSize: 11.5, color: 'var(--fg-muted)', margin: '20px 0 0', lineHeight: 1.5 }}>
          Access reserved for authorized collaborators.
        </p>
      </div>
    </div>
  );
}
