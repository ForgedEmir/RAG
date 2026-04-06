// Oracle des Archives — Script principal

// ── Authentification Supabase ───────────────────────────────────────────────

let supabaseClient = null;
let currentUser = null;

function _authModal() { return document.getElementById('authModal'); }
function _authStatus() { return document.getElementById('authStatus'); }

async function loadAuthConfig() {
    const res = await fetch('/api/auth/config');
    if (!res.ok) throw new Error('Configuration auth indisponible');
    return res.json();
}

async function getAuthToken() {
    if (!supabaseClient) return '';
    const { data } = await supabaseClient.auth.getSession();
    return data?.session?.access_token || '';
}

async function authHeaders(extra = {}) {
    const token = await getAuthToken();
    if (token) {
        return { ...extra, Authorization: `Bearer ${token}` };
    }
    const guestId = currentUser?.id || '';
    if (guestId.startsWith('guest_')) {
        return { ...extra, 'x-local-guest-id': guestId };
    }
    return extra;
}

function setAuthStateUI() {
    const pill = document.getElementById('authPill');
    const emailEl = document.getElementById('authUserEmail');
    if (!pill || !emailEl) return;
    if (!currentUser) {
        pill.style.display = 'none';
        _authModal().style.display = 'flex';
        return;
    }
        let displayText = currentUser.email || 'Utilisateur connecté';
        if (currentUser.id && currentUser.id.startsWith('guest_')) {
            displayText = '👤 Invité (données locales uniquement)';
        }
        emailEl.textContent = displayText;
    pill.style.display = 'flex';
    _authModal().style.display = 'none';
}

async function initAuth() {
    // WHY: On initialise Supabase en premier pour détecter un callback OAuth
    // (token dans le fragment URL). Si on retournait tôt pour le guest, le login
    // GitHub ne pouvait jamais s'enregistrer après un passage en mode invité.
    const cfg = await loadAuthConfig().catch(() => null);

    if (cfg?.supabase_url && cfg?.supabase_anon_key && window.supabase?.createClient) {
        supabaseClient = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
        const { data } = await supabaseClient.auth.getSession();
        const sessionUser = data?.session?.user || null;

        if (sessionUser) {
            // Session réelle (email ou OAuth GitHub) — on efface le mode invité s'il existait
            localStorage.removeItem('oracleGuestId');
            currentUser = sessionUser;
            setAuthStateUI();

            supabaseClient.auth.onAuthStateChange((_event, session) => {
                currentUser = session?.user || null;
                if (currentUser) localStorage.removeItem('oracleGuestId');
                setAuthStateUI();
            });
            return;
        }

        supabaseClient.auth.onAuthStateChange((_event, session) => {
            currentUser = session?.user || null;
            if (currentUser) localStorage.removeItem('oracleGuestId');
            setAuthStateUI();
        });
    }

    // Pas de session Supabase active : vérifier le mode guest local
    const guestId = localStorage.getItem('oracleGuestId');
    if (guestId) {
        currentUser = { id: guestId, email: 'Invit\u00e9' };
        setAuthStateUI();
        return;
    }

    // Ni session ni guest → montrer le modal d'auth
    setAuthStateUI();
}

async function loginWithEmail() {
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    _authStatus().textContent = '';
    if (!email || !password) {
        _authStatus().textContent = 'Email et mot de passe requis.';
        return;
    }

    const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
    _authStatus().textContent = error ? error.message : '';
}

async function signupWithEmail() {
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    _authStatus().textContent = '';
    if (!email || !password) {
        _authStatus().textContent = 'Email et mot de passe requis.';
        return;
    }

    const { error } = await supabaseClient.auth.signUp({ email, password });
    _authStatus().textContent = error
        ? error.message
        : 'Compte créé. Vérifie ta boîte mail si confirmation activée.';
}

async function loginWithGithub() {
    _authStatus().textContent = '';
    const redirectTo = `${window.location.origin}${window.location.pathname}`;
    const { error } = await supabaseClient.auth.signInWithOAuth({
        provider: 'github',
        options: { redirectTo },
    });
    if (error) {
        _authStatus().textContent = error.message;
    }
}

async function logout() {
    // Nettoyer le mode guest s'il existe
    localStorage.removeItem('oracleGuestId');
    currentUser = null;
    setAuthStateUI();
    
    // Logout Supabase s'il est initialisé
    if (supabaseClient) {
        await supabaseClient.auth.signOut();
    }
}

async function continueAsGuest() {
    _authStatus().textContent = '';

    // Option recommandée : vrai compte invité Supabase (JWT valide, scalable)
    try {
        if (!supabaseClient) {
            const cfg = await loadAuthConfig();
            if (cfg.supabase_url && cfg.supabase_anon_key && window.supabase?.createClient) {
                supabaseClient = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
            }
        }

        if (supabaseClient?.auth?.signInAnonymously) {
            const { data, error } = await supabaseClient.auth.signInAnonymously();
            if (!error && data?.user) {
                localStorage.removeItem('oracleGuestId');
                currentUser = data.user;
                setAuthStateUI();
                document.getElementById('userInput').focus();
                return;
            }
        }
    } catch (e) {
        console.warn('Anonymous auth indisponible, fallback local:', e);
    }

    // Fallback local : usage démo/local uniquement (pas recommandé pour la prod)
    const guestId = 'guest_' + generateUUID();
    localStorage.setItem('oracleGuestId', guestId);
    currentUser = { id: guestId, email: 'Invité' };
    setAuthStateUI();
    _authStatus().textContent = 'Mode invité local actif (données locales uniquement).';
    document.getElementById('userInput').focus();
}
function _sessionsKey() {
    return `oracle_sessions_${currentUser?.id || 'guest'}`;
}

function _currentKey() {
    return `oracle_current_session_${currentUser?.id || 'guest'}`;
}

function _historyKey(sessionId) {
    return `oracle_history_${currentUser?.id || 'guest'}_${sessionId}`;
}

function getLocalExchanges(sessionId) {
    try {
        return JSON.parse(localStorage.getItem(_historyKey(sessionId)) || '[]');
    } catch (_) {
        return [];
    }
}

function appendLocalExchange(sessionId, question, answer) {
    const exchanges = getLocalExchanges(sessionId);
    exchanges.push({ question, answer });
    localStorage.setItem(_historyKey(sessionId), JSON.stringify(exchanges));
}

function getSessions() {
    return JSON.parse(localStorage.getItem(_sessionsKey()) || '[]');
}

function saveSessions(sessions) {
    localStorage.setItem(_sessionsKey(), JSON.stringify(sessions));
}

function removeSessionLocally(sessionId) {
    const sessions = getSessions().filter(s => s.id !== sessionId);
    saveSessions(sessions);
}

function getSessionId() {
    let id = localStorage.getItem(_currentKey());
    if (!id) id = startNewSession();
    return id;
}

// Génère un UUID v4 compatible avec tous les navigateurs
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        let r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function startNewSession() {
    const id = (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function')
        ? crypto.randomUUID()
        : generateUUID();
    localStorage.setItem(_currentKey(), id);
    return id;
}

function registerSession(sessionId, firstQuestion) {
    const sessions = getSessions();
    if (sessions.find(s => s.id === sessionId)) return;
    sessions.unshift({ id: sessionId, title: firstQuestion.slice(0, 55), created_at: Date.now() });
    saveSessions(sessions);
    renderSidebar();
}

function formatDate(ts) {
    return new Date(ts).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}

// ── Conditions d'utilisation ────────────────────────────────────────────────

const TERMS_ACCEPTED_KEY = 'oracleTermsAccepted';

function checkTermsAcceptance() {
    const accepted = localStorage.getItem(TERMS_ACCEPTED_KEY);
    document.getElementById('termsModal').style.display = accepted === 'true' ? 'none' : 'flex';
}

function initializeTermsModal() {
    const acceptCheckbox = document.getElementById('acceptTerms');
    const acceptButton   = document.getElementById('acceptTermsButton');

    acceptCheckbox.addEventListener('change', function() {
        acceptButton.disabled = !this.checked;
    });

    acceptButton.addEventListener('click', function() {
        if (acceptCheckbox.checked) {
            localStorage.setItem(TERMS_ACCEPTED_KEY, 'true');
            document.getElementById('termsModal').style.display = 'none';
        }
    });
}

// ── Éléments du DOM ─────────────────────────────────────────────────────────

const userInput        = document.getElementById('userInput');
const revealButton     = document.getElementById('revealButton');
const oracleResponses  = document.getElementById('oracleResponses');
const loadingIndicator = document.getElementById('loadingIndicator');
const sidebar          = document.getElementById('sidebar');
const convList         = document.getElementById('convList');

let isFirstMessage = true;

// ── Sidebar (historique) ────────────────────────────────────────────────────

function renderSidebar() {
    const sessions = getSessions();
    const currentId = localStorage.getItem(_currentKey());
    convList.innerHTML = '';

    if (sessions.length === 0) {
        convList.innerHTML = '<div class="conv-empty">Aucune consultation passée.<br>Posez votre première question à l\'Oracle.</div>';
        return;
    }

    sessions.forEach(s => {
        const item = document.createElement('div');
        item.className = 'conv-item' + (s.id === currentId ? ' active' : '');
        item.innerHTML = `
            <div class="conv-item-title">${s.title}</div>
            <div class="conv-item-date">${formatDate(s.created_at)}</div>
            <button class="conv-item-delete" title="Supprimer">×</button>
        `;
        item.querySelector('.conv-item-delete').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteConversation(s.id);
        });
        item.addEventListener('click', () => loadConversation(s.id));
        convList.appendChild(item);
    });
}

async function loadConversation(sessionId) {
    localStorage.setItem(_currentKey(), sessionId);
    renderSidebar();
    clearResponses();

    try {
        const res = await fetch(`/api/conversations?session_id=${sessionId}`, {
            headers: await authHeaders(),
        });

        if (!res.ok) {
            if (res.status === 403 || res.status === 404) {
                removeSessionLocally(sessionId);
                renderSidebar();
            }
            throw new Error(`HTTP ${res.status}`);
        }

        const data = await res.json();
        if (data.exchanges && data.exchanges.length > 0) {
            isFirstMessage = false;
            data.exchanges.forEach(ex => {
                addUserQuestion(ex.question, true);
                addOracleResponse(ex.answer, true);
            });
            localStorage.setItem(_historyKey(sessionId), JSON.stringify(data.exchanges));
            sidebar.classList.remove('open');
            userInput.focus();
            return;
        }
    } catch (e) {
        console.error('Erreur chargement conversation:', e);
    }

    const localExchanges = getLocalExchanges(sessionId);
    if (localExchanges.length > 0) {
        isFirstMessage = false;
        localExchanges.forEach(ex => {
            addUserQuestion(ex.question, true);
            addOracleResponse(ex.answer, true);
        });
    } else {
        oracleResponses.innerHTML = WELCOME_HTML;
    }

    sidebar.classList.remove('open');
    userInput.focus();
}

const WELCOME_HTML = `
    <div class="oracle-message welcome-message" id="welcomeMessage">
        <div class="oracle-response">
            Salutations, chercheur de vérités cachées. Je suis l'Oracle des Archives, gardien des connaissances perdues dans les méandres du temps.
            <br><br>
            Posez-moi vos questions, et je consulterai les parchemins mystiques pour vous révéler les secrets que vous cherchez.
        </div>
    </div>`;

async function deleteConversation(sessionId) {
    await fetch(`/api/conversations?session_id=${sessionId}`, {
        method: 'DELETE',
        headers: await authHeaders(),
    }).catch(() => {});

    const sessions = getSessions().filter(s => s.id !== sessionId);
    saveSessions(sessions);

    // Si c'était la session active, on en crée une nouvelle
    if (localStorage.getItem(_currentKey()) === sessionId) {
        startNewSession();
        clearResponses();
        oracleResponses.innerHTML = WELCOME_HTML;
    }

    renderSidebar();
}

function clearResponses() {
    oracleResponses.innerHTML = '';
    isFirstMessage = true;
}

// ── Helpers d'affichage ─────────────────────────────────────────────────────

function addUserQuestion(question, fromHistory = false) {
    if (!fromHistory && isFirstMessage) {
        const welcome = document.getElementById('welcomeMessage');
        if (welcome) {
            welcome.classList.add('fade-out');
            setTimeout(() => welcome.parentNode?.removeChild(welcome), 800);
        }
        isFirstMessage = false;
    }
    const div = document.createElement('div');
    div.className = 'oracle-message' + (fromHistory ? ' from-history' : '');
    div.innerHTML = `<div class="user-question">${question}</div>`;
    oracleResponses.appendChild(div);
}

function addBlockedMessage(message, blockType) {
    const isInjection = blockType === 'prompt_injection' || blockType === 'jailbreak';
    const div = document.createElement('div');
    div.className = 'oracle-message';
    div.innerHTML = `
        <div class="oracle-response-blocked ${isInjection ? 'blocked-injection' : 'blocked-offtopic'}">
            ${message}
        </div>`;
    oracleResponses.appendChild(div);
    oracleResponses.scrollTop = oracleResponses.scrollHeight;
}

function addOracleResponse(text, fromHistory = false) {
    const div = document.createElement('div');
    div.className = 'oracle-message' + (fromHistory ? ' from-history' : '');
    const inner = document.createElement('div');
    inner.className = 'oracle-response';
    inner.innerHTML = marked.parse(text);
    div.appendChild(inner);
    oracleResponses.appendChild(div);
    oracleResponses.scrollTop = oracleResponses.scrollHeight;
    return inner;
}

function createStreamingMessage() {
    const div = document.createElement('div');
    div.className = 'oracle-message';
    const inner = document.createElement('div');
    inner.className = 'oracle-response';
    div.appendChild(inner);
    oracleResponses.appendChild(div);
    return inner;
}

async function fetchAndPlayTts(text, onEnd) {
    stopCurrentAudio();
    const res = await fetch('/api/tts', {
        method: 'POST',
        headers: await authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error('TTS indisponible');
    const blob = new Blob([await res.arrayBuffer()], { type: 'audio/mpeg' });
    currentAudio = new Audio(URL.createObjectURL(blob));
    currentAudio.onended = () => { currentAudio = null; onEnd?.(); };
    currentAudio.play();
}

function addTtsButton(textEl) {
    const btn = document.createElement('button');
    btn.className = 'tts-btn';
    btn.textContent = '🔊 Écouter';
    btn.addEventListener('click', async () => {
        if (btn.classList.contains('playing')) {
            stopCurrentAudio();
            btn.classList.remove('playing');
            btn.textContent = '🔊 Écouter';
            return;
        }
        btn.classList.add('playing');
        btn.textContent = '⏹ Arrêter';
        try {
            await fetchAndPlayTts(textEl.textContent, () => {
                btn.classList.remove('playing');
                btn.textContent = '🔊 Écouter';
            });
        } catch (_) {
            btn.classList.remove('playing');
            btn.textContent = '🔊 Écouter';
        }
    });
    textEl.parentNode.appendChild(btn);
}

function showLoading() { loadingIndicator.classList.add('visible'); }
function hideLoading() { loadingIndicator.classList.remove('visible'); }

// ── Confidence score & feedback ──────────────────────────────────────────────

function addConfidenceBadge(msgEl, metaData) {
    if (!metaData) return;
    const confidence = metaData.confidence ?? null;
    const sources    = (metaData.sources || []).join(' · ');
    if (confidence === null && !sources) return;

    const badge = document.createElement('div');
    badge.className = 'confidence-badge';
    const parts = [];
    if (sources) parts.push(`📚 ${sources}`);
    if (confidence !== null) parts.push(`Confiance : ${confidence} %`);
    badge.textContent = parts.join('  ·  ');
    msgEl.parentNode.appendChild(badge);
}

function addFeedbackButtons(msgEl, sessionId) {
    const wrap = document.createElement('div');
    wrap.className = 'feedback-wrap';

    [{ emoji: '👍', rating: 5 }, { emoji: '👎', rating: 1 }].forEach(({ emoji, rating }) => {
        const btn = document.createElement('button');
        btn.className = 'feedback-btn';
        btn.textContent = emoji;
        btn.title = rating >= 4 ? 'Bonne réponse' : 'Réponse incorrecte';
        btn.addEventListener('click', async () => {
            if (wrap.dataset.sent) return;
            wrap.dataset.sent = '1';
            wrap.querySelectorAll('.feedback-btn').forEach(b => b.disabled = true);
            btn.textContent += ' ✔';
            try {
                await fetch('/api/feedback', {
                    method: 'POST',
                    headers: await authHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ session_id: sessionId, rating }),
                });
            } catch (e) {
                console.warn('Feedback error:', e);
            }
        });
        wrap.appendChild(btn);
    });

    msgEl.parentNode.appendChild(wrap);
}

// ── Cooldown anti-spam (5s) ─────────────────────────────────────────────────

let _cooldownTimer = null;

function startCooldown() {
    let remaining = 5;
    revealButton.disabled = true;
    revealButton.textContent = `Patienter... ${remaining}s`;
    _cooldownTimer = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
            clearInterval(_cooldownTimer);
            revealButton.disabled = false;
            revealButton.textContent = 'Révéler';
        } else {
            revealButton.textContent = `Patienter... ${remaining}s`;
        }
    }, 1000);
}

// ── Consultation de l'Oracle ────────────────────────────────────────────────

async function consultOracle() {
    stopCurrentAudio();
    const question = userInput.value.trim();
    if (!question) {
        alert('Veuillez écrire votre question sur le parchemin mystique...');
        return;
    }

    startCooldown();
    const sessionId = getSessionId();
    addUserQuestion(question);
    userInput.value = '';
    showLoading();

    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: await authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ question, session_id: sessionId }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            if (response.status === 429) {
                hideLoading();
                addBlockedMessage(err.error || 'Trop de requêtes.', 'rate_limit');
                return;
            }
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const contentType = response.headers.get('content-type') || '';

        // Réponse bloquée (JSON classique, pas de stream)
        if (!contentType.includes('text/event-stream')) {
            const data = await response.json();
            hideLoading();
            setTimeout(() => {
                if (data.blocked) {
                    addBlockedMessage(data.reponse, data.block_type);
                } else {
                    addOracleResponse(data.reponse);
                    if (getSessions().find(s => s.id === sessionId) === undefined) {
                        registerSession(sessionId, question);
                    }
                    appendLocalExchange(sessionId, question, data.reponse || '');
                }
            }, 500);
            return;
        }

        // Réponse streamée (SSE)
        hideLoading();
        const msgEl = createStreamingMessage();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullText = '';
        let metaData = null;
        let isFirstQuestion = getSessions().find(s => s.id === sessionId) === undefined;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const payload = line.slice(6).trim();
                if (!payload) continue;

                try {
                    const event = JSON.parse(payload);
                    if (event.type === 'meta') {
                        metaData = event;
                    } else if (event.type === 'text') {
                        fullText += event.text;
                        msgEl.textContent = fullText;
                        oracleResponses.scrollTop = oracleResponses.scrollHeight;
                    } else if (event.type === 'done') {
                        msgEl.innerHTML = marked.parse(fullText);
                        if (isFirstQuestion) registerSession(sessionId, question);
                        appendLocalExchange(sessionId, question, fullText);
                        addTtsButton(msgEl);
                        addConfidenceBadge(msgEl, metaData);
                        addFeedbackButtons(msgEl, sessionId);
                        if (voiceMode) { voiceMode = false; autoPlayTts(msgEl); }
                    }
                } catch (_) {}
            }
        }

    } catch (error) {
        console.error('Erreur:', error);
        hideLoading();
        setTimeout(() => addOracleResponse(
            "Les brumes mystiques obscurcissent ma vision... L'Oracle semble être dans un sommeil profond. " +
            "Vérifiez que le serveur des mystères soit éveillé et tentez à nouveau votre invocation."
        ), 500);
    }
}

// ── Mode vocal (STT → RAG → TTS auto) ──────────────────────────────────────

const PTT_KEY     = 'F2';    // Touche push-to-talk
const SILENCE_MS  = 1500;    // Délai silence avant envoi auto (ms)
const SILENCE_THR = 10;      // Seuil silence (0–255)

let mediaRecorder = null;
let audioChunks   = [];
let voiceMode     = false;
let _vadInterval  = null;
let _audioCtx     = null;
let currentAudio  = null;

function stopCurrentAudio() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.src = '';
        currentAudio = null;
    }
}

async function startRecording(pushToTalk = false) {
    if (mediaRecorder?.state === 'recording') return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
        if (_vadInterval) { clearInterval(_vadInterval); _vadInterval = null; }
        if (_audioCtx)    { _audioCtx.close(); _audioCtx = null; }
        stream.getTracks().forEach(t => t.stop());

        const micBtn = document.getElementById('micButton');
        micBtn.textContent = '⏳';
        micBtn.disabled = true;
        micBtn.classList.remove('recording');

        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        const form = new FormData();
        form.append('audio', blob, 'audio.webm');
        try {
            const res  = await fetch('/api/stt', {
                method: 'POST',
                headers: await authHeaders(),
                body: form,
            });
            const data = await res.json();
            if (data.text?.trim()) {
                userInput.value = data.text.trim();
                voiceMode = true;
                consultOracle();
            }
        } catch (err) {
            console.error('STT error:', err);
        } finally {
            micBtn.textContent = '🎤';
            micBtn.disabled = false;
        }
    };
    mediaRecorder.start();

    // Détection de silence (désactivée en push-to-talk)
    if (!pushToTalk) {
        _audioCtx = new AudioContext();
        const analyser = _audioCtx.createAnalyser();
        analyser.fftSize = 512;
        _audioCtx.createMediaStreamSource(stream).connect(analyser);
        const buf = new Uint8Array(analyser.frequencyBinCount);
        let silenceTimer = null;
        let recordingMs  = 0;

        _vadInterval = setInterval(() => {
            recordingMs += 100;
            if (recordingMs < 800) return; // au moins 0.8s avant de détecter le silence

            analyser.getByteFrequencyData(buf);
            const avg = buf.reduce((a, b) => a + b, 0) / buf.length;

            if (avg < SILENCE_THR) {
                if (!silenceTimer) silenceTimer = setTimeout(() => stopRecording(), SILENCE_MS);
            } else {
                if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
            }
        }, 100);
    }
}

function stopRecording() {
    if (mediaRecorder?.state === 'recording') mediaRecorder.stop();
}

async function autoPlayTts(textEl) {
    try { await fetchAndPlayTts(textEl.textContent); } catch (_) {}
}

// ── Initialisation ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
    checkTermsAcceptance();
    initializeTermsModal();

    initAuth().then(() => {
        renderSidebar();
    }).catch((err) => {
        console.error('Auth init error:', err);
        _authStatus().textContent = err.message;
        _authModal().style.display = 'flex';
    });

    document.getElementById('authLoginButton').addEventListener('click', loginWithEmail);
    document.getElementById('authSignupButton').addEventListener('click', signupWithEmail);
    document.getElementById('authGithubButton').addEventListener('click', loginWithGithub);
    document.getElementById('logoutButton').addEventListener('click', logout);

    document.getElementById('authGuestButton').addEventListener('click', continueAsGuest);
    document.getElementById('authPassword').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loginWithEmail();
    });

    document.getElementById('sidebarToggle').addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    document.getElementById('newConvButton').addEventListener('click', () => {
        startNewSession();
        clearResponses();
        oracleResponses.innerHTML = WELCOME_HTML;
        renderSidebar();
        sidebar.classList.remove('open');
        userInput.focus();
    });

    // Micro — clic = mode silence auto
    const micBtn = document.getElementById('micButton');
    micBtn.title = `Clic : silence auto  |  Maintenir ${PTT_KEY} : push-to-talk`;
    micBtn.addEventListener('click', async () => {
        if (mediaRecorder?.state === 'recording') {
            stopRecording();
        } else {
            micBtn.classList.add('recording');
            await startRecording(false);
        }
    });

    // Push-to-talk clavier
    document.addEventListener('keydown', async (e) => {
        if (e.key !== PTT_KEY || e.repeat || mediaRecorder?.state === 'recording') return;
        stopCurrentAudio();
        micBtn.classList.add('recording');
        await startRecording(true);
    });
    document.addEventListener('keyup', (e) => {
        if (e.key !== PTT_KEY) return;
        stopRecording();
    });

    revealButton.addEventListener('click', consultOracle);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); consultOracle(); }
    });
    userInput.focus();
});
