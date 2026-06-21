import { createClient } from '@supabase/supabase-js';

let _supabase = null;

export async function getSupabase() {
  if (_supabase) return _supabase;
  const res = await fetch('/api/auth/config');
  if (!res.ok) return null;
  const { supabase_url, supabase_anon_key } = await res.json();
  if (!supabase_url || !supabase_anon_key) return null;
  _supabase = createClient(supabase_url, supabase_anon_key);
  return _supabase;
}

export async function loginWithEmail(email, password) {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) throw error;
}

export async function signupWithEmail(email, password) {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { error } = await sb.auth.signUp({ email, password });
  if (error) throw error;
  return 'Account created. Check your email if confirmation is enabled.';
}

export async function sendMagicLink(email) {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { error } = await sb.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: window.location.origin + '/auth/callback' },
  });
  if (error) throw error;
}

export async function loginWithGithub() {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const redirectTo = window.location.origin + window.location.pathname;
  const { error } = await sb.auth.signInWithOAuth({ provider: 'github', options: { redirectTo } });
  if (error) throw error;
}

export async function loginWithGoogle() {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const redirectTo = window.location.origin + window.location.pathname;
  const { error } = await sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo } });
  if (error) throw error;
}

export async function loginWithMicrosoft() {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { error } = await sb.auth.signInWithOAuth({
    provider: 'azure',
    options: { redirectTo: window.location.origin + '/chat' },
  });
  if (error) throw error;
}

export async function logout() {
  localStorage.removeItem('rabeliaGuestId');
  localStorage.removeItem('oracleGuestId');
  const sb = await getSupabase();
  if (sb) await sb.auth.signOut();
}

export async function getSession() {
  const sb = await getSupabase();
  if (!sb) return null;
  const { data } = await sb.auth.getSession();
  return data?.session ?? null;
}

export function onAuthStateChange(callback) {
  let unsub = () => {};
  getSupabase().then(sb => {
    if (!sb) return;
    const { data } = sb.auth.onAuthStateChange((_event, session) => {
      callback(session?.user ?? null);
    });
    unsub = () => data.subscription.unsubscribe();
  });
  return () => unsub();
}

export async function getAuthHeader() {
  try {
    const sb = await getSupabase();
    if (sb) {
      const { data } = await sb.auth.getSession();
      const token = data?.session?.access_token;
      if (token) return { Authorization: `Bearer ${token}` };
    }
  } catch (_) {}
  const guestId = localStorage.getItem('rabeliaGuestId') || localStorage.getItem('oracleGuestId') || '';
  if (guestId.startsWith('guest_')) return { 'x-local-guest-id': guestId };
  return {};
}

// ── MFA / TOTP ────────────────────────────────────────────────────────────────

export async function getMfaLevel() {
  const sb = await getSupabase();
  if (!sb) return { currentLevel: 'aal1', nextLevel: 'aal1' };
  const { data, error } = await sb.auth.mfa.getAuthenticatorAssuranceLevel();
  if (error) return { currentLevel: 'aal1', nextLevel: 'aal1' };
  return data;
}

export async function enrollMfa() {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { data, error } = await sb.auth.mfa.enroll({ factorType: 'totp' });
  if (error) throw error;
  return data; // { id, type, totp: { qr_code, secret, uri } }
}

export async function challengeMfa(factorId) {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { data, error } = await sb.auth.mfa.challenge({ factorId });
  if (error) throw error;
  return data; // { id (challengeId) }
}

export async function verifyMfa(factorId, challengeId, code) {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { data, error } = await sb.auth.mfa.verify({ factorId, challengeId, code });
  if (error) throw error;
  return data;
}

export async function unenrollMfa(factorId) {
  const sb = await getSupabase();
  if (!sb) throw new Error('Supabase not configured');
  const { data, error } = await sb.auth.mfa.unenroll({ factorId });
  if (error) throw error;
  return data;
}

export async function listMfaFactors() {
  const sb = await getSupabase();
  if (!sb) return [];
  const { data, error } = await sb.auth.mfa.listFactors();
  if (error) return [];
  return data?.totp || [];
}

export function getOrCreateGuestId() {
  let id = localStorage.getItem('rabeliaGuestId') || localStorage.getItem('oracleGuestId');
  if (!id) {
    const uuid = crypto.randomUUID
      ? crypto.randomUUID()
      : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
          const r = Math.random() * 16 | 0;
          return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
    id = 'guest_' + uuid;
    localStorage.setItem('rabeliaGuestId', id);
  }
  return id;
}
