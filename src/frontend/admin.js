// =====================================================
// Sanctum Administratorum — Interface Admin
// =====================================================

// ── État global ──────────────────────────────────────
const state = {
    currentSection:    'dashboard',
    highlightNodes:    [],
    currentHighlight:  0,
};

// Stockage des données pour les boutons "Voir dans le document"
// Évite les problèmes d'échappement dans les attributs onclick
window._adminViewData = {};

// ── Initialisation ───────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await checkAuth();
    setupNavigation();
    setupDocModal();
    setupUploadZone();

    document.getElementById('loginBtn').addEventListener('click', login);
    document.getElementById('passwordInput').addEventListener('keydown', e => {
        if (e.key === 'Enter') login();
    });
    document.getElementById('logoutBtn').addEventListener('click', logout);
    document.getElementById('quickReindexBtn').addEventListener('click', () => reindex(true));
    document.getElementById('quickUpdateBtn').addEventListener('click', () => reindex(false));
    document.getElementById('refreshFilesBtn').addEventListener('click', loadFiles);
    document.getElementById('searchTestBtn').addEventListener('click', runSearchTest);
    document.getElementById('searchTestInput').addEventListener('keydown', e => {
        if (e.key === 'Enter') runSearchTest();
    });
});

// ── Auth ─────────────────────────────────────────────
async function checkAuth() {
    const res  = await fetch('/api/admin/status');
    const data = await res.json();
    if (data.authenticated) {
        showAdminApp();
    } else {
        showLoginOverlay();
    }
}

async function login() {
    const password = document.getElementById('passwordInput').value;
    const errEl    = document.getElementById('loginError');
    errEl.textContent = '';

    const res = await fetch('/api/admin/login', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ password }),
    });

    if (res.ok) {
        showAdminApp();
    } else {
        const data = await res.json();
        errEl.textContent = data.error || 'Mot de passe incorrect';
    }
}

async function logout() {
    await fetch('/api/admin/logout', { method: 'POST' });
    location.reload();
}

function showLoginOverlay() {
    document.getElementById('loginOverlay').style.display = 'flex';
    document.getElementById('adminApp').style.display     = 'none';
}

function showAdminApp() {
    document.getElementById('loginOverlay').style.display = 'none';
    document.getElementById('adminApp').style.display     = 'flex';
    loadDashboard();
}

// ── Navigation ───────────────────────────────────────
function setupNavigation() {
    document.querySelectorAll('.nav-item[data-section]').forEach(item => {
        item.addEventListener('click', () => navigateTo(item.dataset.section));
    });
}

function navigateTo(section) {
    state.currentSection = section;

    document.querySelectorAll('.nav-item[data-section]').forEach(el => {
        el.classList.toggle('active', el.dataset.section === section);
    });
    document.querySelectorAll('.admin-section').forEach(el => {
        el.classList.toggle('active', el.id === section + 'Section');
    });

    if (section === 'dashboard') loadDashboard();
    if (section === 'files')     loadFiles();
    if (section === 'history')   loadHistory();
}

// ── Dashboard ────────────────────────────────────────
async function loadDashboard() {
    try {
        const res  = await fetch('/api/admin/stats');
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('statVectors').textContent = data.total_vectors ?? '—';
        document.getElementById('statFiles').textContent   = data.file_count    ?? '—';
        document.getElementById('statQueries').textContent = data.query_count   ?? '—';
        document.getElementById('statMode').textContent    =
            (data.mode === 'cloud') ? '☁ Cloud' : '💾 Local';
    } catch (e) {
        console.error('Erreur dashboard:', e);
    }
}

async function reindex(force) {
    const statusEl = document.getElementById('reindexStatus');
    const btn = force
        ? document.getElementById('quickReindexBtn')
        : document.getElementById('quickUpdateBtn');

    btn.disabled = true;
    statusEl.textContent = force
        ? '⏳ Réindexation complète en cours...'
        : '⏳ Mise à jour incrémentale en cours...';
    statusEl.className = 'status-msg';

    try {
        const res  = await fetch('/api/admin/reindex', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ force }),
        });
        const data = await res.json();

        if (res.ok) {
            statusEl.textContent = '✅ ' + data.message;
            statusEl.className   = 'status-msg success';
            showToast(data.message, 'success');
            await loadDashboard();
        } else {
            statusEl.textContent = '❌ ' + (data.error || 'Erreur inconnue');
            statusEl.className   = 'status-msg error';
        }
    } catch {
        statusEl.textContent = '❌ Erreur réseau';
        statusEl.className   = 'status-msg error';
    } finally {
        btn.disabled = false;
    }
}

// ── Files ────────────────────────────────────────────
async function loadFiles() {
    const tbody = document.getElementById('filesTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="table-loading">Consultation des archives...</td></tr>';

    try {
        const res  = await fetch('/api/admin/files');
        if (!res.ok) throw new Error();
        const data = await res.json();

        if (!data.files.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="table-loading">Aucune archive indexée.</td></tr>';
            return;
        }

        tbody.innerHTML = data.files.map(f => {
            const viewKey = 'file_' + f.name;
            window._adminViewData[viewKey] = { source: f.name, passages: [] };
            return `
                <tr>
                    <td><span class="file-name">${escapeHtml(f.name)}</span></td>
                    <td>${formatFileSize(f.size)}</td>
                    <td><span class="chunk-badge">${f.chunks}</span></td>
                    <td>${formatDate(f.modified)}</td>
                    <td>
                        <div class="table-actions">
                            <button class="btn-icon btn-view"
                                onclick="adminViewFile('${escapeHtml(viewKey)}')">
                                👁 Voir
                            </button>
                            <button class="btn-icon btn-delete"
                                onclick="deleteFile('${escapeHtml(f.name)}')">
                                🗑 Supprimer
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch {
        tbody.innerHTML = '<tr><td colspan="5" class="table-loading" style="color:#e07070">Erreur lors du chargement.</td></tr>';
    }
}

async function deleteFile(filename) {
    if (!confirm(`Supprimer "${filename}" des archives ?\n\nCela retirera le fichier et tous ses fragments indexés.`)) return;

    try {
        const res  = await fetch(`/api/admin/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, 'success');
            await loadFiles();
            await loadDashboard();
        } else {
            showToast(data.error || 'Erreur lors de la suppression', 'error');
        }
    } catch {
        showToast('Erreur réseau', 'error');
    }
}

// ── Upload Zone ──────────────────────────────────────
function setupUploadZone() {
    const zone  = document.getElementById('uploadZone');
    const input = document.getElementById('fileInput');

    zone.addEventListener('click', () => input.click());
    input.addEventListener('change', () => uploadFiles(input.files));

    zone.addEventListener('dragover', e => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        uploadFiles(e.dataTransfer.files);
    });
}

async function uploadFiles(fileList) {
    if (!fileList.length) return;

    const statusEl = document.getElementById('uploadStatus');
    statusEl.textContent = `⏳ Import de ${fileList.length} fichier(s)...`;
    statusEl.className   = 'status-msg';

    const formData = new FormData();
    Array.from(fileList).forEach(f => formData.append('files', f));

    try {
        const res  = await fetch('/api/admin/upload', { method: 'POST', body: formData });
        const data = await res.json();

        if (res.ok) {
            const msg = data.message + (data.errors.length ? ` (${data.errors.length} erreur(s))` : '');
            statusEl.textContent = '✅ ' + msg;
            statusEl.className   = 'status-msg success';
            showToast(data.message, 'success');
            await loadFiles();
            await loadDashboard();
        } else {
            statusEl.textContent = '❌ ' + (data.error || 'Erreur upload');
            statusEl.className   = 'status-msg error';
        }
    } catch {
        statusEl.textContent = '❌ Erreur réseau';
        statusEl.className   = 'status-msg error';
    }

    document.getElementById('fileInput').value = '';
}

// ── Search Test ──────────────────────────────────────
async function runSearchTest() {
    const input    = document.getElementById('searchTestInput');
    const question = input.value.trim();
    const results  = document.getElementById('searchResults');

    if (!question) return;

    const btn = document.getElementById('searchTestBtn');
    btn.disabled    = true;
    btn.textContent = '⏳ Recherche...';
    results.innerHTML = '';

    try {
        const res  = await fetch('/api/admin/search-test', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ question }),
        });
        const data = await res.json();

        if (!res.ok) {
            results.innerHTML = `<p class="no-results">Erreur : ${escapeHtml(data.error)}</p>`;
            return;
        }

        if (!data.passages.length) {
            results.innerHTML = '<p class="no-results">Aucun passage trouvé pour cette question.</p>';
            return;
        }

        // Stocker les données de vue (évite l'escaping dans les onclick)
        data.passages.forEach((passage, i) => {
            const source = data.sources[i] || data.sources[0] || 'inconnu';
            const viewKey = `search_${Date.now()}_${i}`;
            window._adminViewData[viewKey] = { source, passages: [passage] };
            data._viewKeys = data._viewKeys || [];
            data._viewKeys.push(viewKey);
        });

        results.innerHTML = data.passages.map((passage, i) => {
            const source  = data.sources[i] || data.sources[0] || 'inconnu';
            const viewKey = data._viewKeys[i];
            return `
                <div class="passage-card">
                    <div class="passage-header">
                        <span class="passage-number">Fragment #${i + 1}</span>
                        <span class="source-badge">📜 ${escapeHtml(source)}</span>
                    </div>
                    <div class="passage-text">${escapeHtml(passage)}</div>
                    <button class="btn-icon btn-view"
                        onclick="adminViewFile('${viewKey}')">
                        👁 Voir dans le document
                    </button>
                </div>
            `;
        }).join('');

    } catch {
        results.innerHTML = '<p class="no-results">Erreur réseau.</p>';
    } finally {
        btn.disabled    = false;
        btn.textContent = '🔍 Rechercher';
    }
}

// ── History ──────────────────────────────────────────
async function loadHistory() {
    const container = document.getElementById('historyContainer');
    container.innerHTML = '<p class="table-loading">Chargement des chroniques...</p>';

    try {
        const res  = await fetch('/api/admin/queries');
        const data = await res.json();

        if (!data.queries.length) {
            container.innerHTML = '<p class="table-loading">Aucune question enregistrée pour cette session.</p>';
            return;
        }

        container.innerHTML = data.queries.map((q, i) => {
            // Pré-enregistrer les données de vue
            const passageButtons = (q.passages || []).map((p, pi) => {
                const src     = q.sources[pi] || q.sources[0] || 'inconnu';
                const viewKey = `hist_${i}_${pi}`;
                window._adminViewData[viewKey] = { source: src, passages: [p] };
                return `
                    <div style="margin-bottom:10px;">
                        <em style="font-size:0.85rem;color:var(--text-muted)">
                            Fragment ${pi + 1} — ${escapeHtml(src)}
                        </em>
                        <div class="passage-text" style="margin-top:4px;">${escapeHtml(p)}</div>
                        <button class="btn-icon btn-view" style="margin-top:4px;"
                            onclick="adminViewFile('${viewKey}')">
                            👁 Voir dans le document
                        </button>
                    </div>
                `;
            }).join('');

            const sourceBadges = (q.sources || []).map(s =>
                `<span class="source-badge">📜 ${escapeHtml(s)}</span>`
            ).join('');

            const blockedBadge = q.blocked
                ? (q.block_type === 'prompt_injection'
                    ? `<span class="block-badge block-injection">⛔ Injection</span>`
                    : `<span class="block-badge block-offtopic">🔮 Hors-sujet</span>`)
                : '';

            const cardClass = q.blocked
                ? `history-card blocked-card ${q.block_type === 'prompt_injection' ? 'blocked-injection' : 'blocked-offtopic'}`
                : 'history-card';

            return `
                <div class="${cardClass}" id="hcard-${i}">
                    <div class="history-card-header" onclick="toggleHistory(${i})">
                        <span class="history-question">✒️ ${escapeHtml(q.question)}</span>
                        <div class="history-meta">
                            ${blockedBadge}
                            <span class="history-time">${formatDate(q.timestamp)}</span>
                            <div class="history-sources">${sourceBadges}</div>
                        </div>
                    </div>
                    <div class="history-card-body">
                        <div class="history-response">${escapeHtml(q.reponse)}</div>
                        ${passageButtons}
                    </div>
                </div>
            `;
        }).join('');
    } catch {
        container.innerHTML = '<p class="table-loading" style="color:#e07070">Erreur de chargement.</p>';
    }
}

function toggleHistory(i) {
    document.getElementById(`hcard-${i}`)?.classList.toggle('expanded');
}

// ── Accès document depuis la clé globale ─────────────
function adminViewFile(key) {
    const d = window._adminViewData[key];
    if (d) viewFile(d.source, d.passages, 0);
}

// ── Document Viewer ──────────────────────────────────
async function viewFile(filename, passages, startIdx) {
    const modal     = document.getElementById('docModal');
    const titleEl   = document.getElementById('docModalTitle');
    const contentEl = document.getElementById('docContent');
    const legendEl  = document.getElementById('docModalLegend');
    const badgeEl   = document.getElementById('docHighlightCount');
    const prevBtn   = document.getElementById('prevHighlight');
    const nextBtn   = document.getElementById('nextHighlight');

    // Réinitialisation
    state.highlightNodes   = [];
    state.currentHighlight = 0;

    titleEl.textContent        = filename;
    contentEl.innerHTML        = '<em style="color:var(--text-muted)">Chargement du parchemin...</em>';
    legendEl.style.display     = 'none';
    badgeEl.style.display      = 'none';
    prevBtn.style.display      = 'none';
    nextBtn.style.display      = 'none';
    modal.style.display        = 'flex';

    try {
        const res  = await fetch(`/api/admin/files/${encodeURIComponent(filename)}/content`);
        const data = await res.json();

        if (!res.ok) {
            contentEl.innerHTML = `<span style="color:var(--danger-light)">${escapeHtml(data.error)}</span>`;
            return;
        }

        const passagesToHighlight = Array.isArray(passages) ? passages.filter(Boolean) : [];
        const { html, found }     = buildHighlightedContent(data.content, passagesToHighlight);
        contentEl.innerHTML       = html;

        if (found > 0) {
            legendEl.style.display = 'flex';
            badgeEl.style.display  = 'inline-block';
            badgeEl.textContent    = `${found} passage${found > 1 ? 's' : ''} trouvé${found > 1 ? 's' : ''}`;

            state.highlightNodes   = Array.from(contentEl.querySelectorAll('.passage-highlight'));
            state.currentHighlight = typeof startIdx === 'number' && startIdx >= 0 ? startIdx : 0;

            if (state.highlightNodes.length > 1) {
                prevBtn.style.display = 'inline-block';
                nextBtn.style.display = 'inline-block';
            }

            // Scroll vers le premier highlight
            setTimeout(() => scrollToHighlight(state.currentHighlight), 80);
        }

    } catch (e) {
        contentEl.innerHTML = '<span style="color:var(--danger-light)">Erreur lors du chargement.</span>';
    }
}

/**
 * Construit le HTML avec les passages mis en évidence.
 * Travaille sur le contenu normalisé (espaces unifiés) pour que les passages
 * extraits par unstructured correspondent au texte brut du fichier.
 */
function buildHighlightedContent(rawContent, passages) {
    const normalize = s => s.replace(/\s+/g, ' ').trim();
    const normalizedContent = normalize(rawContent);

    // Trouver les positions de chaque passage dans le contenu normalisé
    const ranges = [];
    for (let i = 0; i < passages.length; i++) {
        const p = passages[i];
        if (!p || !p.trim()) continue;

        const normalizedPassage = normalize(p);
        if (normalizedPassage.length < 10) continue;

        let pos = normalizedContent.indexOf(normalizedPassage);

        // Fallback : correspondance partielle sur les 80 premiers caractères
        if (pos < 0 && normalizedPassage.length > 80) {
            const prefix = normalizedPassage.slice(0, 80);
            const prefixPos = normalizedContent.indexOf(prefix);
            if (prefixPos >= 0) pos = prefixPos;
        }

        if (pos >= 0) {
            ranges.push({ start: pos, end: pos + normalizedPassage.length, idx: i });
        }
    }

    // Trier et construire le HTML depuis le contenu normalisé
    ranges.sort((a, b) => a.start - b.start);

    let html   = '';
    let cursor = 0;
    let found  = 0;

    for (const { start, end, idx } of ranges) {
        if (start < cursor) continue; // chevauchement, on saute
        html += escapeHtml(normalizedContent.slice(cursor, start));
        html += `<mark class="passage-highlight" data-idx="${idx}">${escapeHtml(normalizedContent.slice(start, end))}</mark>`;
        cursor = end;
        found++;
    }
    html += escapeHtml(normalizedContent.slice(cursor));

    if (found === 0) html = escapeHtml(rawContent);

    return { html, found };
}

function scrollToHighlight(idx) {
    if (!state.highlightNodes.length) return;
    const node = state.highlightNodes[idx];
    if (!node) return;

    state.highlightNodes.forEach(n => n.classList.remove('active-highlight'));
    node.classList.add('active-highlight');
    node.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function setupDocModal() {
    document.getElementById('closeDocModal').addEventListener('click', closeDocModal);
    document.getElementById('docModalOverlay').addEventListener('click', closeDocModal);

    document.getElementById('prevHighlight').addEventListener('click', () => {
        if (!state.highlightNodes.length) return;
        state.currentHighlight =
            (state.currentHighlight - 1 + state.highlightNodes.length) % state.highlightNodes.length;
        scrollToHighlight(state.currentHighlight);
    });

    document.getElementById('nextHighlight').addEventListener('click', () => {
        if (!state.highlightNodes.length) return;
        state.currentHighlight = (state.currentHighlight + 1) % state.highlightNodes.length;
        scrollToHighlight(state.currentHighlight);
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeDocModal();
    });
}

function closeDocModal() {
    document.getElementById('docModal').style.display = 'none';
    document.getElementById('docContent').innerHTML   = '';
    state.highlightNodes   = [];
    state.currentHighlight = 0;
}

// ── Toast Notifications ───────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast     = document.createElement('div');
    toast.className  = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ── Utilitaires ───────────────────────────────────────
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g,  '&amp;')
        .replace(/</g,  '&lt;')
        .replace(/>/g,  '&gt;')
        .replace(/"/g,  '&quot;')
        .replace(/'/g,  '&#39;');
}

function formatFileSize(bytes) {
    if (bytes < 1024)        return bytes + ' o';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' Ko';
    return (bytes / (1024 * 1024)).toFixed(2) + ' Mo';
}

function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleDateString('fr-FR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch { return isoStr; }
}
