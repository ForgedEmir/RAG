/**
 * Hook de chat — sessions et messages persistés dans Supabase via l'API backend.
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import { getSupabase } from './auth.js';

async function buildHeaders() {
  try {
    const sb = await getSupabase();
    if (sb) {
      const { data } = await sb.auth.getSession();
      const token = data?.session?.access_token;
      if (token) return { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
    }
  } catch (_) {}
  const guestId = localStorage.getItem('oracleGuestId') || '';
  const headers = { 'Content-Type': 'application/json' };
  if (guestId.startsWith('guest_')) headers['x-local-guest-id'] = guestId;
  return headers;
}

function newSessionId() {
  return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
}

function flatToMessages(flat) {
  return flat.map((m, i) => ({ id: m.id ?? i, role: m.role, content: m.content }));
}

export function useChat() {
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const abortRef = useRef(null);
  const loadedSessions = useRef(new Set());

  const activeSession = sessions.find(s => s.id === activeId) ?? null;

  // ── Charge la liste des conversations au montage ──────────────────────────
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadingHistory(true);
      try {
        const headers = await buildHeaders();
        const res = await fetch('/api/conversations/list', { headers });
        if (!res.ok || cancelled) return;
        const { conversations } = await res.json();
        if (!cancelled && conversations?.length) {
          setSessions(conversations.map(c => ({
            id: c.id,
            title: c.title || 'Conversation',
            messages: [],
            created_at: c.created_at,
          })));
        }
      } catch (_) {}
      finally { if (!cancelled) setLoadingHistory(false); }
    }
    load();
    return () => { cancelled = true; };
  }, []); // une seule fois au montage

  // ── Charge les messages quand on active une session ───────────────────────
  // On utilise une ref pour éviter la boucle (sessions dans les deps)
  const sessionsRef = useRef(sessions);
  useEffect(() => { sessionsRef.current = sessions; }, [sessions]);

  useEffect(() => {
    if (!activeId || loadedSessions.current.has(activeId)) return;
    const session = sessionsRef.current.find(s => s.id === activeId);
    if (!session) return;
    if (session.messages.length > 0) {
      loadedSessions.current.add(activeId);
      return;
    }
    loadedSessions.current.add(activeId); // marquer tout de suite pour éviter double-load
    let cancelled = false;
    async function load() {
      try {
        const headers = await buildHeaders();
        const res = await fetch(`/api/conversations/messages?session_id=${encodeURIComponent(activeId)}`, { headers });
        if (!res.ok || cancelled) return;
        const { messages } = await res.json();
        if (cancelled || !messages?.length) return;
        setSessions(prev => prev.map(s =>
          s.id === activeId ? { ...s, messages: flatToMessages(messages) } : s
        ));
      } catch (_) {}
    }
    load();
    return () => { cancelled = true; };
  }, [activeId]); // seulement activeId, pas sessions

  const newSession = useCallback(() => {
    const id = newSessionId();
    setSessions(prev => [{ id, title: 'Nouvelle conversation', messages: [] }, ...prev]);
    setActiveId(id);
    loadedSessions.current.add(id);
    return id;
  }, []);

  const selectSession = useCallback((id) => {
    setActiveId(id);
  }, []);

  const deleteSession = useCallback(async (id) => {
    try {
      const headers = await buildHeaders();
      await fetch(`/api/conversations?session_id=${encodeURIComponent(id)}`, { method: 'DELETE', headers });
    } catch (_) {}
    loadedSessions.current.delete(id);
    setSessions(prev => prev.filter(s => s.id !== id));
    setActiveId(prev => prev === id ? null : prev);
  }, []);

  const _addMsg = useCallback((sessionId, msg) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId
        ? {
            ...s,
            title: s.messages.length === 0 && msg.role === 'user'
              ? msg.content.slice(0, 45) + (msg.content.length > 45 ? '…' : '')
              : s.title,
            messages: [...s.messages, msg],
          }
        : s
    ));
  }, []);

  const _patchLast = useCallback((sessionId, patch) => {
    setSessions(prev => prev.map(s => {
      if (s.id !== sessionId) return s;
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last?.role === 'assistant') msgs[msgs.length - 1] = { ...last, ...patch };
      return { ...s, messages: msgs };
    }));
  }, []);

  const send = useCallback(async (question, sessionId) => {
    if (!question.trim() || streaming) return;

    let sid = sessionId;
    if (!sid) {
      sid = newSessionId();
      setSessions(prev => [{ id: sid, title: question.slice(0, 45) + (question.length > 45 ? '…' : ''), messages: [] }, ...prev]);
      setActiveId(sid);
      loadedSessions.current.add(sid);
    }

    _addMsg(sid, { role: 'user', content: question, id: Date.now() });
    _addMsg(sid, { role: 'assistant', content: '', id: Date.now() + 1, streaming: true, sources: [], confidence: null });

    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const headers = await buildHeaders();
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers,
        body: JSON.stringify({ question, session_id: sid }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        _patchLast(sid, { content: err.error || 'Erreur serveur', streaming: false });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '', accumulated = '', sources = [], confidence = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'meta') {
              sources = evt.sources ?? []; confidence = evt.confidence ?? null;
              _patchLast(sid, { sources, confidence });
            } else if (evt.type === 'text') {
              accumulated += evt.text;
              _patchLast(sid, { content: accumulated, sources, confidence });
            } else if (evt.type === 'done') {
              _patchLast(sid, { content: accumulated, streaming: false, sources, confidence });
            } else if (evt.type === 'error') {
              _patchLast(sid, { content: evt.message || 'Erreur', streaming: false });
            }
          } catch (_) {}
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError')
        _patchLast(sid, { content: 'Connexion perdue. Réessaie.', streaming: false });
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
    return sid;
  }, [streaming, _addMsg, _patchLast]);

  const abort = useCallback(() => { abortRef.current?.abort(); }, []);

  return { sessions, activeSession, activeId, streaming, loadingHistory, newSession, selectSession, deleteSession, send, abort };
}
