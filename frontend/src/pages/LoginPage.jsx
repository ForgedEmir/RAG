import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import RabeliaLogo from '../components/RabeliaLogo.jsx';
import Icon from '../components/Icon.jsx';
import { loginWithEmail, sendMagicLink, getMfaLevel, listMfaFactors, challengeMfa, verifyMfa } from '../auth.js';

export default function LoginPage({ onLogin }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState('magic'); // 'magic' | 'password'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  // 2FA state
  const [mfaStep, setMfaStep] = useState(null); // null | { factorId, challengeId }
  const [totpCode, setTotpCode] = useState('');
  const navigate = useNavigate();

  const handlePassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await loginWithEmail(email, password);
      // Check if MFA is required
      const assurance = await getMfaLevel();
      if (assurance.nextLevel === 'aal2' && assurance.currentLevel !== 'aal2') {
        const factors = await listMfaFactors();
        if (factors.length > 0) {
          const factor = factors[0];
          const challenge = await challengeMfa(factor.id);
          setMfaStep({ factorId: factor.id, challengeId: challenge.id });
          setLoading(false);
          return;
        }
      }
      navigate('/chat');
    } catch (err) {
      setError(err.message || t('login.error_login'));
    } finally {
      setLoading(false);
    }
  };

  const handleMfaVerify = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await verifyMfa(mfaStep.factorId, mfaStep.challengeId, totpCode.replace(/\s/g, ''));
      navigate('/chat');
    } catch (err) {
      setError(err.message || t('login.error_invalid_code'));
    } finally {
      setLoading(false);
    }
  };

  const handleMagicLink = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await sendMagicLink(email);
      setSuccess(t('login.magic_success', { email }));
    } catch (err) {
      setError(err.message || t('login.error_send'));
    } finally {
      setLoading(false);
    }
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
        {t('login.title')}
      </div>
      <div style={{
        position: 'absolute', bottom: 24, left: 28, right: 28,
        display: 'flex', justifyContent: 'space-between',
        fontSize: 11, color: 'var(--fg-muted)',
      }}>
        <span>{t('login.copyright')}</span>
        <span>{t('login.support')}</span>
      </div>

      <div style={{ width: 380, textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
          <RabeliaLogo size="lg" />
        </div>

        <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 8px', letterSpacing: '-0.015em' }}>
          {t('login.heading')}
        </h1>
        <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 24px', lineHeight: 1.55 }}>
          {t('login.subtitle')}
        </p>

        <div style={{
          display: 'flex', gap: 4, marginBottom: 24,
          background: 'var(--bg-sunken)', borderRadius: 8, padding: 4,
        }}>
          <button
            type="button"
            onClick={() => { setMode('magic'); setError(''); setSuccess(''); }}
            style={{
              flex: 1, padding: '7px 0', fontSize: 12, fontWeight: 500,
              border: 'none', borderRadius: 6, cursor: 'pointer',
              background: mode === 'magic' ? 'var(--bg-surface)' : 'transparent',
              color: mode === 'magic' ? 'var(--fg-primary)' : 'var(--fg-muted)',
              boxShadow: mode === 'magic' ? '0 1px 3px rgba(0,0,0,0.12)' : 'none',
              transition: 'all 0.15s',
            }}
          >
            {t('login.tab_magic')}
          </button>
          <button
            type="button"
            onClick={() => { setMode('password'); setError(''); setSuccess(''); }}
            style={{
              flex: 1, padding: '7px 0', fontSize: 12, fontWeight: 500,
              border: 'none', borderRadius: 6, cursor: 'pointer',
              background: mode === 'password' ? 'var(--bg-surface)' : 'transparent',
              color: mode === 'password' ? 'var(--fg-primary)' : 'var(--fg-muted)',
              boxShadow: mode === 'password' ? '0 1px 3px rgba(0,0,0,0.12)' : 'none',
              transition: 'all 0.15s',
            }}
          >
            {t('login.tab_password')}
          </button>
        </div>

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

        {success && (
          <div style={{
            marginBottom: 16, padding: '10px 14px',
            background: 'var(--ok-soft)', border: '1px solid var(--ok)',
            borderRadius: 'var(--r-md)', fontSize: 13, color: 'var(--ok)',
            textAlign: 'left', display: 'flex', gap: 8, alignItems: 'flex-start',
          }}>
            <Icon name="check" size={15} style={{ flex: 'none', marginTop: 1 }} />
            {success}
          </div>
        )}

        {mfaStep ? (
          <form onSubmit={handleMfaVerify} style={{ textAlign: 'left' }}>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 16px', lineHeight: 1.55 }}>
              {t('login.mfa_prompt')}
            </p>
            <div style={{ marginBottom: 16 }}>
              <label className="rb-label">{t('login.mfa_label')}</label>
              <input
                className="rb-input rb-input--lg"
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={totpCode}
                onChange={e => setTotpCode(e.target.value.replace(/\D/g, ''))}
                placeholder="000000"
                autoComplete="one-time-code"
                required
                style={{ letterSpacing: '0.3em', textAlign: 'center', fontSize: 20 }}
              />
            </div>
            <button
              type="submit"
              className="rb-btn rb-btn--primary rb-btn--lg rb-btn--block"
              disabled={loading || totpCode.length < 6}
            >
              {loading ? t('login.verifying') : t('login.confirm')}
            </button>
            <button
              type="button"
              onClick={() => { setMfaStep(null); setTotpCode(''); setError(''); }}
              style={{ width: '100%', marginTop: 8, background: 'none', border: 'none', color: 'var(--fg-muted)', fontSize: 12, cursor: 'pointer', padding: '4px 0' }}
            >
              {t('login.back')}
            </button>
          </form>
        ) : mode === 'magic' ? (
          <form onSubmit={handleMagicLink} style={{ textAlign: 'left' }}>
            <div style={{ marginBottom: 16 }}>
              <label className="rb-label" htmlFor="email-magic">{t('login.email_label')}</label>
              <input
                id="email-magic"
                className="rb-input rb-input--lg"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder={t('login.email_placeholder')}
                autoComplete="email"
                required
              />
            </div>
            <button
              type="submit"
              className="rb-btn rb-btn--primary rb-btn--lg rb-btn--block"
              disabled={loading || !!success}
            >
              {loading ? t('login.sending') : success ? t('login.link_sent') : t('login.magic_btn')}
            </button>
            <p style={{ fontSize: 12, color: 'var(--fg-muted)', margin: '10px 0 0', textAlign: 'center' }}>
              {t('login.magic_helper')}
            </p>
          </form>
        ) : (
          <form onSubmit={handlePassword} style={{ textAlign: 'left' }}>
            <div style={{ marginBottom: 12 }}>
              <label className="rb-label" htmlFor="email-pwd">{t('login.email_label')}</label>
              <input
                id="email-pwd"
                className="rb-input rb-input--lg"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder={t('login.email_placeholder')}
                autoComplete="email"
                required
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label className="rb-label" htmlFor="password">{t('login.password_label')}</label>
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
              {loading ? t('login.logging_in') : t('login.btn_login')}
            </button>
          </form>
        )}

        <p style={{ fontSize: 11.5, color: 'var(--fg-muted)', margin: '24px 0 0', lineHeight: 1.5 }}>
          {t('login.footer')}
        </p>
      </div>
    </div>
  );
}
