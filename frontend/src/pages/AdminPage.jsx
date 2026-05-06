import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getAuthHeader } from '../auth.js';
import Icon from '../components/Icon.jsx';
import RabeliaLogo from '../components/RabeliaLogo.jsx';

export default function AdminPage({ user, onLogout }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteMsg, setInviteMsg] = useState('');
  const [inviteError, setInviteError] = useState('');

  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'A';

  const fetchUsers = async () => {
    setLoadingUsers(true);
    try {
      const headers = await getAuthHeader();
      const res = await fetch('/api/admin/users', { headers });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setUsers(data.users || []);
    } catch (_) {
      setUsers([]);
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleInvite = async (e) => {
    e.preventDefault();
    setInviteLoading(true);
    setInviteMsg('');
    setInviteError('');
    try {
      const headers = await getAuthHeader();
      const res = await fetch('/api/admin/users/invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...headers },
        body: JSON.stringify({ email: inviteEmail }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Error');
      }
      setInviteMsg(t('admin.invite_success'));
      setInviteEmail('');
      fetchUsers();
    } catch (err) {
      setInviteError(err.message);
    } finally {
      setInviteLoading(false);
    }
  };

  const handleDelete = async (userId, email) => {
    if (!confirm(t('admin.delete_confirm', { email }))) return;
    try {
      const headers = await getAuthHeader();
      await fetch(`/api/admin/users/${userId}`, { method: 'DELETE', headers });
      fetchUsers();
    } catch (_) {}
  };

  const fmt = (iso) => {
    if (!iso) return t('admin.never');
    return new Date(iso).toLocaleDateString();
  };

  return (
    <div style={{ height: '100vh', display: 'grid', gridTemplateColumns: '260px 1fr', background: 'var(--bg-app)' }}>
      {/* Sidebar */}
      <aside style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border-default)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px 14px 14px', borderBottom: '1px solid var(--border-subtle)' }}>
          <RabeliaLogo size="md" />
        </div>
        <nav style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div
            className="rb-listitem"
            onClick={() => navigate('/chat')}
            style={{ height: 32, padding: '0 10px', gap: 10 }}
          >
            <Icon name="chat" size={15} style={{ color: 'var(--fg-secondary)' }} />
            <span className="rb-listitem__name">{t('admin.back')}</span>
          </div>
          <div
            className="rb-listitem rb-listitem--active"
            style={{ height: 32, padding: '0 10px', gap: 10, cursor: 'default' }}
          >
            <Icon name="shield" size={15} style={{ color: 'var(--accent)' }} />
            <span className="rb-listitem__name">{t('nav.admin')}</span>
          </div>
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="rb-mono rb-mono--user">{userInitials}</div>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || ''}
            </div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} onClick={onLogout} title={t('docs.logout')}>
            <Icon name="logout" size={14} />
          </button>
        </div>
      </aside>

      {/* Main */}
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <header style={{
          height: 56, padding: '0 24px', flexShrink: 0,
          display: 'flex', alignItems: 'center',
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-surface)',
        }}>
          <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{t('admin.heading')}</h1>
        </header>

        <div className="rb-scroll" style={{ flex: 1, overflowY: 'auto', padding: '28px 32px' }}>
          <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 28 }}>

            {/* Invite */}
            <div className="rb-card" style={{ padding: '20px 24px' }}>
              <h2 style={{ fontSize: 13, fontWeight: 600, margin: '0 0 14px' }}>{t('admin.invite_heading')}</h2>
              <form onSubmit={handleInvite} style={{ display: 'flex', gap: 8 }}>
                <input
                  className="rb-input"
                  type="email"
                  value={inviteEmail}
                  onChange={e => setInviteEmail(e.target.value)}
                  placeholder={t('admin.invite_placeholder')}
                  required
                  style={{ flex: 1 }}
                />
                <button
                  type="submit"
                  className="rb-btn rb-btn--primary"
                  disabled={inviteLoading}
                >
                  {inviteLoading ? '...' : t('admin.invite_btn')}
                </button>
              </form>
              {inviteMsg && (
                <div style={{ marginTop: 10, fontSize: 12, color: 'var(--ok)' }}>{inviteMsg}</div>
              )}
              {inviteError && (
                <div style={{ marginTop: 10, fontSize: 12, color: 'var(--danger)' }}>{inviteError}</div>
              )}
            </div>

            {/* Users table */}
            <div className="rb-card" style={{ overflow: 'hidden' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
                <h2 style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>{t('admin.users_heading')}</h2>
              </div>
              {loadingUsers ? (
                <div style={{ padding: '20px 24px', fontSize: 13, color: 'var(--fg-muted)' }}>{t('settings.team_loading')}</div>
              ) : users.length === 0 ? (
                <div style={{ padding: '20px 24px', fontSize: 13, color: 'var(--fg-muted)' }}>{t('settings.team_no_members')}</div>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                  <thead>
                    <tr style={{ background: 'var(--bg-sunken)' }}>
                      {[t('admin.col_email'), t('admin.col_joined'), t('admin.col_last_active'), ''].map((h, i) => (
                        <th key={i} style={{ padding: '8px 16px', fontWeight: 500, textAlign: i === 3 ? 'right' : 'left', color: 'var(--fg-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u, i) => (
                      <tr key={u.id} style={{ borderTop: i === 0 ? 'none' : '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '10px 16px', color: 'var(--fg-primary)' }}>{u.email}</td>
                        <td style={{ padding: '10px 16px', color: 'var(--fg-secondary)' }}>{fmt(u.created_at)}</td>
                        <td style={{ padding: '10px 16px', color: 'var(--fg-secondary)' }}>{fmt(u.last_sign_in_at)}</td>
                        <td style={{ padding: '10px 16px', textAlign: 'right' }}>
                          <button
                            className="rb-btn rb-btn--danger"
                            style={{ fontSize: 11, padding: '4px 10px', height: 'auto' }}
                            onClick={() => handleDelete(u.id, u.email)}
                          >
                            {t('admin.delete_btn')}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
