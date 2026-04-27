-- ============================================================
-- Oracle LoreKeeper — Schéma Supabase (documentation)
-- Ce fichier documente la structure réelle de la DB.
-- NE PAS ré-exécuter si les tables existent déjà.
-- ============================================================

-- =========================
-- CONVERSATIONS (sessions)
-- =========================
CREATE TABLE conversations (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID NOT NULL,
    session_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id    ON conversations(user_id);
CREATE INDEX idx_conversations_session_id ON conversations(session_id);

-- =========================
-- MESSAGES (contenu réel)
-- =========================
CREATE TABLE messages (
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
-- USER MEMORY (mémoire long-terme)
-- =========================
CREATE TABLE user_memory (
    user_id    UUID PRIMARY KEY,
    summary    TEXT DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- EVENTS (monitoring)
-- =========================
CREATE TABLE events (
    id         BIGSERIAL PRIMARY KEY,
    type       VARCHAR NOT NULL,
    detail     TEXT,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =========================
-- RLS (Row Level Security)
-- Utiliser la clé service_role côté backend pour bypasser le RLS.
-- =========================
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_memory   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "conversations_policy" ON conversations FOR ALL
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "messages_policy" ON messages FOR ALL
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY "user_memory_policy" ON user_memory FOR ALL
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- =========================
-- FEEDBACK (Human-in-the-Loop)
-- =========================
CREATE TABLE feedback (
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

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "feedback_policy" ON feedback FOR ALL
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

