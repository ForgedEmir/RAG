import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';
import { getAuthHeader } from '../auth.js';
import {
  getMfaLevel, listMfaFactors, enrollMfa,
  challengeMfa, verifyMfa, unenrollMfa,
} from '../auth.js';

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

function TeamTab({ user, t }) {
  const ROLE_LABELS = { owner: t('settings.team_role_owner'), admin: t('settings.team_role_admin'), member: t('settings.team_role_member'), viewer: t('settings.team_role_viewer') };
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
      setInviteMsg(res.message || t('settings.team_invite_sent', { email: inviteEmail }));
      setInviteEmail('');
      fetchMembers();
    } catch (e) {
      setInviteErr(e.message);
    } finally {
      setInviting(false);
    }
  };

  const handleRemove = async (memberId) => {
    if (!confirm(t('settings.team_remove_confirm'))) return;
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
      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>{t('settings.team_invite_heading')}</h3>
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
            <label className="rb-label">{t('settings.team_email')}</label>
            <input className="rb-input" type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder={t('settings.team_email_placeholder')} required />
          </div>
          <div style={{ flex: 1, minWidth: 140 }}>
            <label className="rb-label">{t('settings.team_role')}</label>
            <select className="rb-input" value={inviteRole} onChange={e => setInviteRole(e.target.value)} style={{ cursor: 'pointer' }}>
              <option value="admin">{t('settings.team_role_admin')}</option>
              <option value="member">{t('settings.team_role_member')}</option>
              <option value="viewer">{t('settings.team_role_viewer')}</option>
            </select>
          </div>
          <button type="submit" className="rb-btn rb-btn--primary" disabled={inviting} style={{ flexShrink: 0, height: 36 }}>
            {inviting ? t('settings.team_inviting') : t('settings.team_invite')}
          </button>
        </form>
      </div>

      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>{t('settings.team_active_members')}</h3>
        {loading ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{t('settings.team_loading')}</div>
        ) : error ? (
          <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>
        ) : members.length === 0 ? (
          <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{t('settings.team_no_members')}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {members.map((m, i) => (
              <div key={m.user_id || i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 6, background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle, rgba(0,0,0,0.02))' }}>
                <div style={{ width: 30, height: 30, borderRadius: '50%', flexShrink: 0, background: 'var(--accent-soft)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 600 }}>
                  {(m.email || '?').slice(0, 2).toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {m.email || m.user_id}
                    {m.is_me && <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--fg-muted)' }}>{t('settings.team_you')}</span>}
                  </div>
                </div>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: m.role === 'owner' ? 'rgba(94,210,156,0.12)' : 'var(--bg-muted)', color: m.role === 'owner' ? 'var(--accent)' : 'var(--fg-secondary)', fontWeight: 500 }}>
                  {ROLE_LABELS[m.role] || m.role}
                </span>
                {!m.is_me && m.role !== 'owner' && (
                  <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0, color: 'var(--danger)' }} onClick={() => handleRemove(m.user_id)} title={t('settings.team_remove')}>
                    <Icon name="trash" size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {pending.length > 0 && (
        <div className="rb-card" style={{ padding: '20px 24px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>{t('settings.team_pending')}</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {pending.map((inv, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 6, background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle, rgba(0,0,0,0.02))' }}>
                <div style={{ width: 30, height: 30, borderRadius: '50%', flexShrink: 0, background: 'var(--bg-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="mail" size={13} style={{ color: 'var(--fg-muted)' }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{inv.email}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{t('settings.team_expires', { date: new Date(inv.expires_at).toLocaleDateString() })}</div>
                </div>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'var(--bg-muted)', color: 'var(--fg-secondary)', fontWeight: 500 }}>{ROLE_LABELS[inv.role] || inv.role}</span>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'rgba(250,204,21,0.12)', color: '#b45309', fontWeight: 500 }}>{t('settings.team_pending_status')}</span>
                <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0, color: 'var(--fg-muted)' }} onClick={() => handleCancelInvite(inv.email)} title={t('settings.team_cancel')}>
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

// ── API Tab ───────────────────────────────────────────────────────────────────

function ApiTab({ t }) {
  const [keys, setKeys]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [newKeyName, setNewKeyName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState(null);
  const [error, setError]       = useState('');

  const fetchKeys = useCallback(async () => {
    try { setLoading(true); const d = await apiFetch('/api/tenant/api-keys'); setKeys(d.keys || []); setError(''); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true); setError(''); setCreatedKey(null);
    try {
      const res = await apiFetch('/api/tenant/api-keys', { method: 'POST', body: JSON.stringify({ name: newKeyName || 'Default' }) });
      setCreatedKey(res.api_key);
      setNewKeyName('');
      fetchKeys();
    } catch (e) { setError(e.message); }
    finally { setCreating(false); }
  };

  const handleRevoke = async (keyId) => {
    if (!confirm(t('settings.api_revoke_confirm'))) return;
    try { await apiFetch(`/api/tenant/api-keys/${keyId}`, { method: 'DELETE' }); fetchKeys(); }
    catch (e) { alert(e.message); }
  };

  const copyKey = (key) => { navigator.clipboard.writeText(key).then(() => alert(t('settings.api_copied'))); };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 720 }}>
      {createdKey && (
        <div style={{ padding: '16px 20px', background: 'var(--ok-soft)', border: '1px solid var(--ok)', borderRadius: 8 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--ok)' }}>{t('settings.api_key_created')}</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <code style={{ flex: 1, padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: 6, fontSize: 12, fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{createdKey}</code>
            <button className="rb-btn rb-btn--primary" style={{ flexShrink: 0, height: 32, fontSize: 12 }} onClick={() => copyKey(createdKey)}>{t('settings.api_copy')}</button>
          </div>
        </div>
      )}

      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>{t('settings.api_create_heading')}</h3>
        <p style={{ fontSize: 12, color: 'var(--fg-muted)', margin: '0 0 12px', lineHeight: 1.5 }}
          dangerouslySetInnerHTML={{ __html: t('settings.api_description') }}
        />
        {error && <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 6, fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
        <form onSubmit={handleCreate} style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label className="rb-label">{t('settings.api_name_label')}</label>
            <input className="rb-input" value={newKeyName} onChange={e => setNewKeyName(e.target.value)} placeholder={t('settings.api_name_placeholder')} />
          </div>
          <button type="submit" className="rb-btn rb-btn--primary" disabled={creating} style={{ height: 36, flexShrink: 0 }}>{creating ? t('settings.api_creating') : t('settings.api_generate')}</button>
        </form>
      </div>

      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 16px' }}>{t('settings.api_active_keys')}</h3>
        {loading ? <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{t('settings.team_loading')}</div> :
         keys.length === 0 ? <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{t('settings.api_no_keys')}</div> :
         <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {keys.filter(k => k.is_active).map((k, i) => (
            <div key={k.id || i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', borderRadius: 6, background: i % 2 === 0 ? 'transparent' : 'var(--bg-subtle)' }}>
              <Icon name="key" size={14} style={{ color: 'var(--fg-muted)' }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{k.name}</div>
                <code style={{ fontSize: 11, color: 'var(--fg-muted)', fontFamily: 'var(--font-mono)' }}>{k.key_prefix}••••••••</code>
                {k.last_used && <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--fg-muted)' }}>{t('settings.api_last_used', { date: new Date(k.last_used).toLocaleDateString() })}</span>}
              </div>
              <button className="rb-btn rb-btn--ghost" style={{ fontSize: 12, color: 'var(--danger)' }} onClick={() => handleRevoke(k.id)}>{t('settings.api_revoke')}</button>
            </div>
          ))}
        </div>}
      </div>
    </div>
  );
}

// ── Usage Tab ─────────────────────────────────────────────────────────────────

function UsageTab({ t }) {
  const [usage, setUsage]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const me = await apiFetch('/api/tenant/me');
        if (me.tenant) {
          const metrics = await apiFetch('/api/admin/metrics');
          const myUsage = metrics.tenants.find(t => t.tenant_id === me.tenant.id);
          setUsage({ tenant: me.tenant, usage: myUsage });
        } else {
          setUsage({ tenant: null, usage: null });
        }
        setError('');
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div style={{ color: 'var(--fg-muted)', fontSize: 13, padding: 20 }}>{t('settings.usage_loading')}</div>;
  if (error) return <div style={{ color: 'var(--danger)', fontSize: 13, padding: 20 }}>{error}</div>;
  if (!usage?.tenant) return (
    <div style={{ padding: 40, textAlign: 'center' }}>
      <div style={{ fontSize: 13, color: 'var(--fg-muted)', marginBottom: 8 }}>{t('settings.usage_no_tenant')}</div>
      <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>{t('settings.usage_no_tenant_helper')}</div>
    </div>
  );

  const u = usage.usage;
  const fmtTokens = (n) => n >= 1_000_000 ? `${(n/1_000_000).toFixed(1)}M` : n >= 1_000 ? `${(n/1_000).toFixed(1)}k` : String(n);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 720 }}>
      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 4px' }}>{usage.tenant.name}</h3>
        <div style={{ fontSize: 12, color: 'var(--fg-muted)' }}>
          {t('settings.usage_plan', { plan: usage.tenant.plan, slug: usage.tenant.slug })}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        {[
          { label: t('settings.usage_requests'), value: u ? u.week_requests.toLocaleString() : '0', icon: 'chat' },
          { label: t('settings.usage_tokens'),   value: u ? fmtTokens(u.week_tokens) : '0', icon: 'zap' },
          { label: t('settings.usage_members'), value: '—', icon: 'users' },
        ].map((m, i) => (
          <div key={i} className="rb-card" style={{ padding: '16px 20px', textAlign: 'center' }}>
            <Icon name={m.icon} size={18} style={{ color: 'var(--fg-muted)', marginBottom: 8, display: 'block', margin: '0 auto 8px' }} />
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{m.value}</div>
            <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginTop: 4 }}>{m.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Security Tab ──────────────────────────────────────────────────────────────

function SecurityTab({ t }) {
  const [factors, setFactors]     = useState([]);
  const [mfaLevel, setMfaLevel]   = useState(null);
  const [step, setStep]           = useState('idle');
  const [enrollData, setEnrollData] = useState(null);
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
    setError(''); setSuccess(''); setLoading(true);
    try {
      const data = await enrollMfa();
      setEnrollData(data);
      const chal = await challengeMfa(data.id);
      setChallengeId(chal.id);
      setStep('verifying');
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      await verifyMfa(enrollData.id, challengeId, totpCode.replace(/\s/g, ''));
      setStep('idle'); setEnrollData(null); setTotpCode('');
      setSuccess(t('settings.security_activated_msg'));
      refresh();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const handleUnenroll = async (factorId) => {
    if (!confirm(t('settings.security_deactivate_confirm'))) return;
    setError('');
    try { await unenrollMfa(factorId); setSuccess(t('settings.security_deactivated_msg')); refresh(); }
    catch (e) { setError(e.message); }
  };

  const verified = factors.filter(f => f.status === 'verified');
  const unverified = factors.filter(f => f.status !== 'verified');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 560 }}>
      <div className="rb-card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>{t('settings.security_heading')}</h3>
          {!loading && (
            <span style={{ fontSize: 11, padding: '2px 10px', borderRadius: 20, fontWeight: 600, background: verified.length > 0 ? 'rgba(94,210,156,0.12)' : 'var(--bg-muted)', color: verified.length > 0 ? 'var(--accent)' : 'var(--fg-muted)' }}>
              {verified.length > 0 ? t('settings.security_enabled') : t('settings.security_disabled')}
            </span>
          )}
        </div>
        {error && <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--danger-soft)', border: '1px solid var(--danger)', borderRadius: 6, fontSize: 13, color: 'var(--danger)' }}>{error}</div>}
        {success && <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--ok-soft)', border: '1px solid var(--ok)', borderRadius: 6, fontSize: 13, color: 'var(--ok)' }}>{success}</div>}
        {loading ? <div style={{ color: 'var(--fg-muted)', fontSize: 13 }}>{t('settings.security_loading')}</div> :
         step === 'verifying' && enrollData ? (
          <div>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 16px', lineHeight: 1.6 }}>{t('settings.security_qr_prompt')}</p>
            {enrollData.totp?.qr_code && <div style={{ margin: '0 auto 16px', width: 'fit-content', padding: 12, background: '#fff', borderRadius: 8 }}><img src={enrollData.totp.qr_code} alt={t('settings.security_qr_alt')} style={{ display: 'block', width: 160, height: 160 }} /></div>}
            {enrollData.totp?.secret && <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--bg-muted)', borderRadius: 6, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--fg-secondary)', textAlign: 'center', letterSpacing: '0.1em' }}>{enrollData.totp.secret}</div>}
            <form onSubmit={handleVerify}>
              <label className="rb-label">{t('settings.security_code_label')}</label>
              <input className="rb-input rb-input--lg" type="text" inputMode="numeric" maxLength={6} value={totpCode} onChange={e => setTotpCode(e.target.value.replace(/\D/g, ''))} placeholder="000000" autoComplete="one-time-code" required style={{ letterSpacing: '0.3em', textAlign: 'center', fontSize: 20, marginBottom: 12 }} />
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" className="rb-btn rb-btn--ghost" style={{ flex: 1 }} onClick={() => { setStep('idle'); setEnrollData(null); setTotpCode(''); }}>{t('settings.security_cancel')}</button>
                <button type="submit" className="rb-btn rb-btn--primary" style={{ flex: 2 }} disabled={loading || totpCode.length < 6}>{loading ? t('settings.security_verifying') : t('settings.security_activate')}</button>
              </div>
            </form>
          </div>
        ) : verified.length > 0 ? (
          <div>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 16px', lineHeight: 1.6 }}>{t('settings.security_active_desc')}</p>
            {verified.map(f => (
              <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: 'var(--bg-muted)', borderRadius: 6 }}>
                <Icon name="shield" size={16} style={{ color: 'var(--accent)' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{f.friendly_name || t('settings.security_authenticator')}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-muted)' }}>{t('settings.security_active_since', { date: f.created_at ? new Date(f.created_at).toLocaleDateString() : '—' })}</div>
                </div>
                <button className="rb-btn rb-btn--ghost" style={{ fontSize: 12, color: 'var(--danger)' }} onClick={() => handleUnenroll(f.id)}>{t('settings.security_deactivate')}</button>
              </div>
            ))}
          </div>
        ) : (
          <div>
            <p style={{ fontSize: 13, color: 'var(--fg-secondary)', margin: '0 0 20px', lineHeight: 1.6 }}>{t('settings.security_inactive_desc')}</p>
            <button className="rb-btn rb-btn--primary" onClick={handleEnroll} disabled={loading}><Icon name="shield" size={14} style={{ marginRight: 6 }} />{t('settings.security_configure')}</button>
          </div>
        )}
        {unverified.length > 0 && step !== 'verifying' && (
          <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border-subtle)', fontSize: 12, color: 'var(--fg-muted)' }}>
            {t('settings.security_unverified', { count: unverified.length })}
            <button style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: 12, padding: 0 }} onClick={() => unverified.forEach(f => unenrollMfa(f.id).then(refresh).catch(() => {}))}>{t('settings.security_clean')}</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SettingsPage({ user, onLogout }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState('team');
  const navigate = useNavigate();
  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'G';

  const TABS = [
    { id: 'team', label: t('settings.tab_team'), icon: 'users' },
    { id: 'api', label: t('settings.tab_api'), icon: 'key' },
    { id: 'usage', label: t('settings.tab_usage'), icon: 'chart' },
    { id: 'security', label: t('settings.tab_security'), icon: 'shield' },
  ];

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateColumns: '260px 1fr', background: 'var(--bg-app)' }}>
      <aside style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border-default)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px 14px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
          <RabeliaLogo size="md" />
        </div>
        <nav style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {[
            { label: t('docs.nav_conversations'), icon: 'chat', path: '/chat' },
            { label: t('docs.nav_documents'), icon: 'folder', path: '/docs' },
            { label: t('docs.nav_settings'), icon: 'settings', path: '/settings', active: true },
          ].map(item => (
            <div key={item.path} className={'rb-listitem' + (item.active ? ' rb-listitem--active' : '')} onClick={() => navigate(item.path)} style={{ height: 32, padding: '0 10px', gap: 10 }}>
              <Icon name={item.icon} size={15} style={{ color: item.active ? 'var(--accent)' : 'var(--fg-secondary)' }} />
              <span className="rb-listitem__name">{item.label}</span>
            </div>
          ))}
        </nav>
        <div style={{ padding: '8px 12px' }}>
          <div style={{ height: 1, background: 'var(--border-subtle)', marginBottom: 8 }} />
          <div className="rb-section-label" style={{ padding: 0, marginBottom: 6 }}>{t('settings.sections')}</div>
          {TABS.map(tt => (
            <div key={tt.id} className={'rb-listitem' + (tab === tt.id ? ' rb-listitem--active' : '')} onClick={() => setTab(tt.id)} style={{ height: 30, padding: '0 8px', gap: 8 }}>
              <Icon name={tt.icon} size={14} style={{ color: tab === tt.id ? 'var(--accent)' : 'var(--fg-secondary)' }} />
              <span className="rb-listitem__name" style={{ fontSize: 12.5 }}>{tt.label}</span>
            </div>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="rb-mono rb-mono--user">{userInitials}</div>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.email || t('docs.user_guest')}</div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} onClick={onLogout} title={t('docs.logout')}>
            <Icon name="logout" size={14} />
          </button>
        </div>
      </aside>
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <header style={{ height: 56, padding: '0 24px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-default)', background: 'var(--bg-surface)' }}>
          <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{t('settings.heading')}</h1>
        </header>
        <div className="rb-scroll" style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
          {tab === 'team'     && <TeamTab user={user} t={t} />}
          {tab === 'api'      && <ApiTab t={t} />}
          {tab === 'usage'    && <UsageTab t={t} />}
          {tab === 'security' && <SecurityTab t={t} />}
        </div>
      </div>
    </div>
  );
}
