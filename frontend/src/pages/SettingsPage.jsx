import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';
import { getAuthHeader } from '../auth.js';
import {
  getMfaLevel, listMfaFactors, enrollMfa,
  challengeMfa, verifyMfa, unenrollMfa,
} from '../auth.js';

const TABS = [
  { id: 'team', label: 'Équipe', icon: 'users' },
  { id: 'security', label: 'Sécurité', icon: 'shield' },
];

async function apiFetch(path, options = {}) {
  const authHeaders = await getAuthHeader();
  const res = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...authHeaders, ...(options.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Team Tab ──────────────────────────────────────────────────────────────────

const ROLE_LABELS = { owner: 'Propriétaire', admin: 'Admin', member: 'Membre', viewer: 'Lecteur' };

function TeamTab({ user }) {
  const [members, setMembers]   = useState([]);
  const [pending, setPending]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole]   = useState('member');
  const [inviting, setInviting]       = useState(false);
  const [inviteMsg, setInviteMsg]     = useState('');
  const [inviteErr, setInviteErr]     = useState('');

  const fetchMembers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch('/api/team/members');
      setMembers(data.members || []);
      setPending(data.pending_invitations || []);
      setError('');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchMembers(); }, [fetchMembers]);

  const handleInvite = async (e) => {
    e.preventDefault();
    setInviting(true);
    setInviteMsg('');
    setInviteErr('');
    try {
      const res = await apiFetch('/api/team/invite', {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail, role: inviteRole }),
      });
      setInviteMsg(res.message || `Invitation envoyée à ${inviteEmail}.`);
      setInviteEmail('');
      fetchMembers();
    } catch (e) {
      setInviteErr(e.message);
    } finally {
      setInviting(false);
    }
  };

  const handleRemove = async (memberId) => {
    if (!confirm('Retirer ce membre de votre espace ?')) return;
    try {
      await apiFetch(`/api/team/members/${memberId}`, { method: 'DELETE' });
      fetchMembers();
    } catch (e) {
      alert(e.message);
    }
  };

  const handleCancelInvite = async (email) => {
    try {
      await apiFetch(`/api/team/invitations/${encodeURIComponent(email)}`, { method: 'DELETE' });
      fetchMembers();
    } catch (e) {
      alert(e.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 720 }}>
      {/* Invite form */}
      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>Inviter un collaborateur</h3>
        {inviteMsg && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--ok-soft)', border: '1px solid var(--ok)', borderRadius: 6, fontSize: 13, color: 'var(--ok)' }}>
            {inviteMsg}
          </div>
        )}
        {inviteErr && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 6, fontSize: 13, color: 'var(--danger)' }}>
            {inviteErr}
          </div>
        )}
        <form onSubmit={handleInvite} style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: 2, minWidth: 200 }}>
            <label className="rb-label">Email</label>
            <input
              className="rb-input"
              type="email"
              value={inviteEmail}
              onChange={e => setInviteEmail(e.target.value)}
              placeholder="colleague@company.com"
              required
            />
          </div>
          <div style={{ flex: 1, minWidth: 140 }}>
            <label className="rb-label">Rôle</label>
            <select
              className="rb-input"
              value={inviteRole}
              onChange={e => setInviteRole(e.target.value)}
              style={{ cursor: 'pointer' }}
            >
              <option value="admin">Admin</option>
              <option value="member">Membre</option>
              <option value="viewer">Lecteur</option>
            </select>
          </div>
          <button
            type="submit"
            className="rb-btn rb-btn--primary"
            disabled={inviting}
            style={{ flexShrink: 0, height: 36 }}
          >
            {inviting ? 'Envoi…' : 'Inviter'}
          </button>
        </form>
      </div>

      {/* Members list */}
      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>Membres actifs</h3>
        {loading ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Chargement…</div>
        ) : error ? (
          <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>
        ) : members.length === 0 ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Aucun membre pour l'instant.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {members.map((m, i) => (
              <div key={m.user_id || i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 12px', borderRadius: 6,
                background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle, rgba(0,0,0,0.02))',
              }}>
                <div style={{
                  width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
                  background: 'var(--accent-soft)', color: 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600,
                }}>
                  {(m.email || '?').slice(0, 2).toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {m.email || m.user_id}
                    {m.is_me && <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--fg-muted)' }}>(vous)</span>}
                  </div>
                </div>
                <span style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 20,
                  background: m.role === 'owner' ? 'rgba(94,210,156,0.12)' : 'var(--bg-muted)',
                  color: m.role === 'owner' ? 'var(--accent)' : 'var(--fg-secondary)',
                  fontWeight: 500,
                }}>
                  {ROLE_LABELS[m.role] || m.role}
                </span>
                {!m.is_me && m.role !== 'owner' && (
                  <button
                    className="rb-btn rb-btn--ghost"
                    style={{ width: 28, height: 28, padding: 0, color: 'var(--danger)' }}
                    onClick={() => handleRemove(m.user_id)}
                    title="Retirer"
                  >
                    <Icon name="trash" size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pending invitations */}
      {pending.length > 0 && (
        <div className="rb-card" style={{ padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>Invitations en attente</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {pending.map((inv, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 12px', borderRadius: 6,
                background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle, rgba(0,0,0,0.02))',
              }}>
                <div style={{ width: 30, height: 30, borderRadius: '50%', flexShrink: 0, background: 'var(--bg-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="mail" size={13} style={{ color: 'var(--fg-muted)' }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{inv.email}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Expire le {new Date(inv.expires_at).toLocaleDateString()}</div>
                </div>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'var(--bg-muted)', color: 'var(--fg-secondary)', fontWeight: 500 }}>
                  {ROLE_LABELS[inv.role] || inv.role}
                </span>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'rgba(250,204,21,0.12)', color: '#b45309', fontWeight: 500 }}>En attente</span>
                <button
                  className="rb-btn rb-btn--ghost"
                  style={{ width: 28, height: 28, padding: 0, color: 'var(--fg-muted)' }}
                  onClick={() => handleCancelInvite(inv.email)}
                  title="Annuler"
                >
                  <Icon name="x" size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Security Tab ──────────────────────────────────────────────────────────────

function SecurityTab() {
  const [factors, setFactors]     = useState([]);
  const [mfaLevel, setMfaLevel]   = useState(null);
  const [step, setStep]           = useState('idle'); // 'idle'|'enrolling'|'verifying'
  const [enrollData, setEnrollData] = useState(null); // { id, totp }
  const [totpCode, setTotpCode]   = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [success, setSuccess]     = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [level, facs] = await Promise.all([getMfaLevel(), listMfaFactors()]);
      setMfaLevel(level);
      setFactors(facs);
    } catch (_) {}
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleEnroll = async () => {
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const data = await enrollMfa();
      setEnrollData(data);
      const chal = await challengeMfa(data.id);
      setChallengeId(chal.id);
      setStep('verifying');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await verifyMfa(enrollData.id, challengeId, totpCode.replace(/\s/g, ''));
      setStep('idle');
      setEnrollData(null);
      setTotpCode('');
      setSuccess('Double authentification activée avec succès.');
      refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUnenroll = async (factorId) => {
    if (!confirm('Désactiver la double authentification ?')) return;
    setError('');
    try {
      await unenrollMfa(factorId);
      setSuccess('Double authentification désactivée.');
      refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const verified = factors.filter(f => f.status === 'verified');
  const unverified = factors.filter(f => f.status !== 'verified');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 560 }}>
      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Double authentification (TOTP)</h3>
          {!loading && (
            <span style={{
              fontSize: 11, padding: '2px 10px', borderRadius: 20, fontWeight: 600,
              background: verified.length > 0 ? 'rgba(94,210,156,0.12)' : 'var(--bg-muted)',
              color: verified.length > 0 ? 'var(--accent)' : 'var(--fg-muted)',
            }}>
              {verified.length > 0 ? 'Activée' : 'Désactivée'}
            </span>
          )}
        </div>

        {error && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 6, fontSize: 13, color: 'var(--danger)' }}>
            {error}
          </div>
        )}
        {success && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--ok-soft)', border: '1px solid var(--ok)', borderRadius: 6, fontSize: 13, color: 'var(--ok)' }}>
            {success}
          </div>
        )}

        {loading ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>Chargement…</div>
        ) : step === 'verifying' && enrollData ? (
          <div>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 16px', lineHeight: 1.6 }}>
              Scannez ce QR code avec votre application d'authentification (Google Authenticator, Authy, 1Password…), puis entrez le code à 6 chiffres pour confirmer.
            </p>
            {enrollData.totp?.qr_code && (
              <div style={{ margin: '0 auto 16px', width: 'fit-content', padding: 12, background: '#fff', borderRadius: 8 }}>
                <img src={enrollData.totp.qr_code} alt="QR Code 2FA" style={{ display: 'block', width: 160, height: 160 }} />
              </div>
            )}
            {enrollData.totp?.secret && (
              <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--bg-muted)', borderRadius: 6, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--fg-secondary)', textAlign: 'center', letterSpacing: '0.1em' }}>
                {enrollData.totp.secret}
              </div>
            )}
            <form onSubmit={handleVerify}>
              <label className="rb-label">Code de vérification</label>
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
                style={{ letterSpacing: '0.3em', textAlign: 'center', fontSize: 20, marginBottom: 12 }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  type="button"
                  className="rb-btn rb-btn--ghost"
                  style={{ flex: 1 }}
                  onClick={() => { setStep('idle'); setEnrollData(null); setTotpCode(''); }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="rb-btn rb-btn--primary"
                  style={{ flex: 2 }}
                  disabled={loading || totpCode.length < 6}
                >
                  {loading ? 'Vérification…' : 'Activer la 2FA'}
                </button>
              </div>
            </form>
          </div>
        ) : verified.length > 0 ? (
          <div>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 16px', lineHeight: 1.6 }}>
              Votre compte est protégé par une double authentification. Un code TOTP sera demandé à chaque connexion par mot de passe.
            </p>
            {verified.map(f => (
              <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: 'var(--bg-muted)', borderRadius: 6 }}>
                <Icon name="shield" size={16} style={{ color: 'var(--accent)' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{f.friendly_name || 'Authenticator app'}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>Actif depuis {f.created_at ? new Date(f.created_at).toLocaleDateString() : '—'}</div>
                </div>
                <button
                  className="rb-btn rb-btn--ghost"
                  style={{ fontSize: 12, color: 'var(--danger)' }}
                  onClick={() => handleUnenroll(f.id)}
                >
                  Désactiver
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 20px', lineHeight: 1.6 }}>
              Ajoutez une couche de sécurité supplémentaire. Une fois activée, un code à usage unique sera requis à chaque connexion par mot de passe.
            </p>
            <button
              className="rb-btn rb-btn--primary"
              onClick={handleEnroll}
              disabled={loading}
            >
              <Icon name="shield" size={14} style={{ marginRight: 6 }} />
              Configurer la double authentification
            </button>
          </div>
        )}

        {/* Pending unverified factors cleanup */}
        {unverified.length > 0 && step !== 'verifying' && (
          <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', fontSize: 12, color: 'var(--fg-muted)' }}>
            {unverified.length} facteur(s) non confirmé(s) —{' '}
            <button
              style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: 12, padding: 0 }}
              onClick={() => unverified.forEach(f => unenrollMfa(f.id).then(refresh).catch(() => {}))}
            >
              Nettoyer
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SettingsPage({ user, onLogout }) {
  const [tab, setTab] = useState('team');
  const navigate = useNavigate();
  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'G';

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateColumns: '260px 1fr', background: 'var(--bg-app)' }}>
      {/* Sidebar */}
      <aside style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border-default)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px 14px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
          <RabeliaLogo size="md" />
        </div>
        <nav style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[
            { label: 'Conversations', icon: 'chat', path: '/chat' },
            { label: 'Documents', icon: 'folder', path: '/docs' },
            { label: 'Paramètres', icon: 'settings', path: '/settings', active: true },
          ].map(item => (
            <div
              key={item.path}
              className={'rb-listitem' + (item.active ? ' rb-listitem--active' : '')}
              onClick={() => navigate(item.path)}
              style={{ height: 32, padding: '0 10px', gap: 10 }}
            >
              <Icon name={item.icon} size={15} style={{ color: item.active ? 'var(--accent)' : 'var(--fg-secondary)' }} />
              <span className="rb-listitem__name">{item.label}</span>
            </div>
          ))}
        </nav>
        <div style={{ padding: '8px 12px' }}>
          <div style={{ height: 1, background: 'var(--border-subtle)', marginBottom: 8 }} />
          <div className="rb-section-label" style={{ padding: 0, marginBottom: 6 }}>Sections</div>
          {TABS.map(t => (
            <div
              key={t.id}
              className={'rb-listitem' + (tab === t.id ? ' rb-listitem--active' : '')}
              onClick={() => setTab(t.id)}
              style={{ height: 30, padding: '0 8px', gap: 8 }}
            >
              <Icon name={t.icon} size={14} style={{ color: tab === t.id ? 'var(--accent)' : 'var(--fg-secondary)' }} />
              <span className="rb-listitem__name" style={{ fontSize: 12.5 }}>{t.label}</span>
            </div>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="rb-mono rb-mono--user">{userInitials}</div>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || 'Invité'}
            </div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} onClick={onLogout} title="Déconnexion">
            <Icon name="logout" size={14} />
          </button>
        </div>
      </aside>

      {/* Main */}
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <header style={{
          height: 56, padding: '0 24px', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-surface)',
        }}>
          <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Paramètres</h1>
        </header>
        <div className="rb-scroll" style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
          {tab === 'team'     && <TeamTab user={user} />}
          {tab === 'security' && <SecurityTab />}
        </div>
      </div>
    </div>
  );
}
