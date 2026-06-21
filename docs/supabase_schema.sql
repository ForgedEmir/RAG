-- ============================================================
-- Oracle LoreKeeper — Schéma Supabase v1.2
-- Ajouts: tenants, api_keys, usage_metrics
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
    key_hash    VARCHAR(64) NOT NULL UNIQUE,          -- SHA256 du préfixe (on stocke pas la clé entière)
    key_prefix  VARCHAR(12) NOT NULL,                  -- 8 premiers caractères pour affichage
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
-- RLS
-- =========================
ALTER TABLE tenants       ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles    ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys      ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_metrics ENABLE ROW LEVEL SECURITY;

-- Le backend utilise la service_role key → bypass RLS automatiquement
-- Pour les appels client-side, ces policies s'appliquent:
CREATE POLICY "tenants_owner" ON tenants FOR ALL
    USING (auth.uid() = owner_id);

CREATE POLICY "user_roles_self" ON user_roles FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "invitations_self" ON invitations FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM user_roles WHERE user_id = auth.uid()
        AND tenant_id = invitations.tenant_id AND role IN ('owner', 'admin')
    ));
