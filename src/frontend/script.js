// Oracle des Archives - JavaScript Interface

// ── Gestion multi-sessions ────────────────────────────────────────────────
const SESSIONS_KEY = 'oracle_sessions';
const CURRENT_KEY  = 'oracle_current_session';

function getSessions() {
    return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]');
}

function saveSessions(sessions) {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

function getSessionId() {
    let id = localStorage.getItem(CURRENT_KEY);
    if (!id) id = startNewSession();
    return id;
}

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
    localStorage.setItem(CURRENT_KEY, id);
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

// ── Terms and Conditions ──────────────────────────────────────────────────
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

// ── DOM refs ──────────────────────────────────────────────────────────────
const userInput        = document.getElementById('userInput');
const revealButton     = document.getElementById('revealButton');
const oracleResponses  = document.getElementById('oracleResponses');
const loadingIndicator = document.getElementById('loadingIndicator');
const sidebar          = document.getElementById('sidebar');
const convList         = document.getElementById('convList');

let isFirstMessage = true;

// ── Sidebar ───────────────────────────────────────────────────────────────
function renderSidebar() {
    const sessions = getSessions();
    const currentId = localStorage.getItem(CURRENT_KEY);
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
    localStorage.setItem(CURRENT_KEY, sessionId);
    renderSidebar();
    clearResponses();

    try {
        const res = await fetch(`/api/conversations?session_id=${sessionId}`);
        const data = await res.json();
        if (data.exchanges && data.exchanges.length > 0) {
            isFirstMessage = false;
            data.exchanges.forEach(ex => {
                addUserQuestion(ex.question, true);
                addOracleResponse(ex.answer, true);
            });
        }
    } catch (e) {
        console.error('Erreur chargement conversation:', e);
    }

    sidebar.classList.remove('open');
    userInput.focus();
}

async function deleteConversation(sessionId) {
    // Supprimer de Supabase
    await fetch(`/api/conversations?session_id=${sessionId}`, { method: 'DELETE' }).catch(() => {});

    // Supprimer du localStorage
    const sessions = getSessions().filter(s => s.id !== sessionId);
    saveSessions(sessions);

    // Si c'était la session active, en démarrer une nouvelle
    if (localStorage.getItem(CURRENT_KEY) === sessionId) {
        startNewSession();
        clearResponses();
        oracleResponses.innerHTML = `
            <div class="oracle-message welcome-message" id="welcomeMessage">
                <div class="oracle-response">
                    Salutations, chercheur de vérités cachées. Je suis l'Oracle des Archives, gardien des connaissances perdues dans les méandres du temps.
                    <br><br>
                    Posez-moi vos questions, et je consulterai les parchemins mystiques pour vous révéler les secrets que vous cherchez.
                </div>
            </div>`;
    }

    renderSidebar();
}

function clearResponses() {
    oracleResponses.innerHTML = '';
    isFirstMessage = true;
}

// ── UI helpers ────────────────────────────────────────────────────────────
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

function addTtsButton(textEl) {
    const btn = document.createElement('button');
    btn.className = 'tts-btn';
    btn.textContent = '🔊 Écouter';
    btn.addEventListener('click', async () => {
        // Si déjà en lecture → stop
        if (btn.classList.contains('playing')) {
            stopCurrentAudio();
            btn.classList.remove('playing');
            btn.textContent = '🔊 Écouter';
            return;
        }
        stopCurrentAudio();
        btn.classList.add('playing');
        btn.textContent = '⏹ Arrêter';
        try {
            const res = await fetch('/api/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: textEl.textContent }),
            });
            if (!res.ok) throw new Error('TTS indisponible');
            const blob = new Blob([await res.arrayBuffer()], { type: 'audio/mpeg' });
            currentAudio = new Audio(URL.createObjectURL(blob));
            currentAudio.onended = () => {
                btn.classList.remove('playing');
                btn.textContent = '🔊 Écouter';
                currentAudio = null;
            };
            currentAudio.play();
        } catch (e) {
            btn.classList.remove('playing');
            btn.textContent = '🔊 Écouter';
        }
    });
    textEl.parentNode.appendChild(btn);
}

function showLoading() { loadingIndicator.classList.add('visible'); }
function hideLoading() { loadingIndicator.classList.remove('visible'); }

// ── Cooldown anti-spam (5 secondes) ──────────────────────────────────────
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

// ── Consultation de l'Oracle ──────────────────────────────────────────────
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
            headers: { 'Content-Type': 'application/json' },
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

        // ── Réponse bloquée (JSON) ────────────────────────────────────────
        if (!contentType.includes('text/event-stream')) {
            const data = await response.json();
            hideLoading();
            setTimeout(() => {
                if (data.blocked) addBlockedMessage(data.reponse, data.block_type);
                else addOracleResponse(data.reponse);
            }, 500);
            return;
        }

        // ── Réponse streamée (SSE) ────────────────────────────────────────
        hideLoading();
        const msgEl = createStreamingMessage();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullText = '';
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
                    if (event.type === 'text') {
                        fullText += event.text;
                        msgEl.textContent = fullText;
                        oracleResponses.scrollTop = oracleResponses.scrollHeight;
                    } else if (event.type === 'done') {
                        msgEl.innerHTML = marked.parse(fullText);
                        if (isFirstQuestion) registerSession(sessionId, question);
                        addTtsButton(msgEl);
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

// ── Mode vocal (STT → RAG → TTS auto) ────────────────────────────────────
const PTT_KEY     = 'F2';          // Touche push-to-talk (configurable)
const SILENCE_MS  = 1500;          // Délai silence avant envoi auto (ms)
const SILENCE_THR = 10;            // Seuil silence (0–255)

let mediaRecorder = null;
let audioChunks   = [];
let voiceMode     = false;
let _vadInterval  = null;
let _audioCtx     = null;
let currentAudio  = null;   // lecture TTS en cours

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
            const res  = await fetch('/api/stt', { method: 'POST', body: form });
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

    // ── Détection de silence (désactivée en push-to-talk) ──────────────────
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
            if (recordingMs < 800) return;   // laisse au moins 0.8s avant de détecter

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
    stopCurrentAudio();
    try {
        const res = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: textEl.textContent }),
        });
        if (!res.ok) return;
        const blob = new Blob([await res.arrayBuffer()], { type: 'audio/mpeg' });
        currentAudio = new Audio(URL.createObjectURL(blob));
        currentAudio.onended = () => { currentAudio = null; };
        currentAudio.play();
    } catch (_) {}
}

// ── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    checkTermsAcceptance();
    initializeTermsModal();
    renderSidebar();

    document.getElementById('sidebarToggle').addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });

    document.getElementById('newConvButton').addEventListener('click', () => {
        startNewSession();
        clearResponses();
        oracleResponses.innerHTML = `
            <div class="oracle-message welcome-message" id="welcomeMessage">
                <div class="oracle-response">
                    Salutations, chercheur de vérités cachées. Je suis l'Oracle des Archives, gardien des connaissances perdues dans les méandres du temps.
                    <br><br>
                    Posez-moi vos questions, et je consulterai les parchemins mystiques pour vous révéler les secrets que vous cherchez.
                </div>
            </div>`;
        renderSidebar();
        sidebar.classList.remove('open');
        userInput.focus();
    });

    // Bouton micro — clic = mode silence auto
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

    // Push-to-talk clavier — maintenir PTT_KEY pour parler
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
