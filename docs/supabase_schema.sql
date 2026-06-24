-- ============================================================
-- RABELIA - Schema Supabase complet (v2.0)
--
-- Fusionne les tables B2B multi-tenant (tenants, user_roles, invitations,
-- api_keys, usage_metrics) avec les tables legacy (conversations, messages,
-- user_memory, events, feedback) utilisees par le code applicatif.
--
-- Ce fichier est destine aux NOUVEAUX deploiements. Si les tables existent
-- deja, NE PAS re-executer ce script (utilisez ALTER TABLE manuellement).
-- ============================================================

-- =========================
-- TENANTS (entreprises B2B)
-- =========================
CREATE TABLE IF NOT EXISTS tenants (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    slug         VARCHAR(100) NOT NULL UNIQUE,       -- ex: "acme-corp"
    owner_id     UUID NOT NULL,                       -- Supabase auth user
    plan         VARCHAR(20) DEFAULT 'free',          -- free, pro, enterprise
    max_users    INT DEFAULT 5,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenants_owner ON tenants(owner_id);
CREATE INDEX idx_tenants_slug  ON tenants(slug);


-- =========================
-- USER ROLES (appartenance tenant)
-- =========================
CREATE TABLE IF NOT EXISTS user_roles (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID NOT NULL,
    tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role       VARCHAR(20) DEFAULT 'member',         -- owner, admin, member, viewer
    invited_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, tenant_id)
);

CREATE INDEX idx_user_roles_tenant ON user_roles(tenant_id);
CREATE INDEX idx_user_roles_user   ON user_roles(user_id);


-- =========================
-- INVITATIONS (en attente)
-- =========================
CREATE TABLE IF NOT EXISTS invitations (
    id          BIGSERIAL PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role        VARCHAR(20) DEFAULT 'member',
    invited_by  UUID,
    token       UUID DEFAULT gen_random_uuid(),
    accepted_at TIMESTAMPTZ,
    expires_at  TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days'),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_invitations_tenant ON invitations(tenant_id);
CREATE INDEX idx_invitations_email  ON invitations(email);


-- =========================
-- API KEYS (par tenant)
-- =========================
CREATE TABLE IF NOT EXISTS api_keys (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(255) DEFAULT 'Default',
    key_hash    VARCHAR(64) NOT NULL UNIQUE,
    key_prefix  VARCHAR(12) NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    last_used   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE INDEX idx_api_keys_tenant ON api_keys(tenant_id);


-- =========================
-- USAGE METRICS (par tenant / jour)
-- =========================
CREATE TABLE IF NOT EXISTS usage_metrics (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    date          DATE NOT NULL DEFAULT CURRENT_DATE,
    requests      INT DEFAULT 0,
    tokens_input  BIGINT DEFAULT 0,
    tokens_output BIGINT DEFAULT 0,
    storage_bytes BIGINT DEFAULT 0,
    UNIQUE(tenant_id, date)
);

CREATE INDEX idx_usage_tenant_date ON usage_metrics(tenant_id, date);


-- =========================
-- CONVERSATIONS (sessions utilisateur)
-- =========================
-- NOTE: pas de colonne tenant_id ici (evite une migration DB).
-- L'isolation tenant se fait en filtrant par user_roles.created_at (date de
-- join tenant) au niveau applicatif (voir get_user_conversations / conversation_belongs_to_user).
CREATE TABLE IF NOT EXISTS conversations (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID NOT NULL,
    session_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id    ON conversations(user_id);
CREATE INDEX idx_conversations_session_id ON conversations(session_id);


-- =========================
-- MESSAGES (contenu des conversations)
-- =========================
CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL,
    role            VARCHAR NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_created ON messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_user_id              ON messages(user_id);


-- =========================
-- USER MEMORY (summary long-terme)
-- =========================
-- NOTE: user_id est TEXT (pas UUID) car le code stocke une cle composite
-- "{tenant_id}:{user_id}" pour isoler les summaries par tenant sans migration
-- de schema (voir tracker.get_user_summary / save_user_summary).
-- En mode single-tenant (tenant_id vide), la cle est juste user_id (UUID).
CREATE TABLE IF NOT EXISTS user_memory (
    user_id    TEXT PRIMARY KEY,
    summary    TEXT DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- =========================
-- EVENTS (monitoring)
-- =========================
CREATE TABLE IF NOT EXISTS events (
    id         BIGSERIAL PRIMARY KEY,
    type       VARCHAR NOT NULL,
    detail     TEXT,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_type_created ON events(type, created_at DESC);


-- =========================
-- FEEDBACK (Human-in-the-Loop)
-- =========================
CREATE TABLE IF NOT EXISTS feedback (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL,
    user_id     UUID NOT NULL,
    rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT DEFAULT '',
    judge_score FLOAT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_session_id ON feedback(session_id);
CREATE INDEX idx_feedback_user_id    ON feedback(user_id);


-- =========================
-- RLS (Row Level Security)
-- Le backend utilise la service_role key -> bypass RLS automatiquement.
-- Les policies ci-dessous s'appliquent aux appels client-side (frontend Supabase JS).
-- =========================
ALTER TABLE tenants       ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles    ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys      ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_memory   ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback      ENABLE ROW LEVEL SECURITY;

-- B2B tables
CREATE POLICY "tenants_owner" ON tenants FOR ALL
    USING (auth.uid() = owner_id);

CREATE POLICY "user_roles_self" ON user_roles FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "invitations_self" ON invitations FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM user_roles WHERE user_id = auth.uid()
        AND tenant_id = invitations.tenant_id AND role IN ('owner', 'admin')
    ));

-- Legacy tables (user-scoped)
CREATE POLICY "conversations_policy" ON conversations FOR ALL
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "messages_policy" ON messages FOR ALL
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- NOTE: user_memory.user_id est TEXT (cle composite tenant:user), la policy
-- RLS sur auth.uid() (UUID) ne peut pas matcher directement. Le backend
-- gere l'isolation via la service_role key (bypass RLS). Pour les appels
-- client-side, ajouter une policy basee sur un prefixe si necessaire.
CREATE POLICY "feedback_policy" ON feedback FOR ALL
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
