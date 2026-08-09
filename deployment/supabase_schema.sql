-- ============================================================
-- AI OS - Supabase schema (run ONCE in Supabase SQL Editor)
--
-- Creates the exact tables the backend + Cloudflare worker expect.
-- Run this before pointing the Cloudflare worker at Supabase.
-- The backend also auto-creates these on first boot (idempotent),
-- so this is belt-and-braces; it guarantees the queue works even
-- before the Hugging Face Space has booted for the first time.
-- ============================================================

-- WhatsApp inbox queue (Cloudflare worker writes, HF Space worker reads)
CREATE TABLE IF NOT EXISTS wa_inbox (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(50) NOT NULL,
    msg_type VARCHAR(20) NOT NULL DEFAULT 'text',
    text TEXT DEFAULT '',
    media_uri TEXT DEFAULT '',
    media_mime VARCHAR(100) DEFAULT '',
    media_name VARCHAR(255) DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    reply_text TEXT DEFAULT '',
    error TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Conversations (long-term memory)
CREATE TABLE IF NOT EXISTS conversations (
    session_id VARCHAR(255) PRIMARY KEY,
    phone_number VARCHAR(50) NOT NULL,
    messages JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User memories
CREATE TABLE IF NOT EXISTS user_memories (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    memory_text TEXT NOT NULL,
    memory_type VARCHAR(50) DEFAULT 'general',
    importance REAL DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    assignee VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(50),
    action VARCHAR(100) NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Auto-update timestamps on conversations
CREATE OR REPLACE FUNCTION update_conversations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversations_updated_at ON conversations;
CREATE TRIGGER trg_conversations_updated_at
BEFORE UPDATE ON conversations
FOR EACH ROW EXECUTE FUNCTION update_conversations_updated_at();

-- Allow RLS to be toggled later; keep it open for the service_role key
ALTER TABLE wa_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service role access wa_inbox" ON wa_inbox
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service role access conversations" ON conversations
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service role access user_memories" ON user_memories
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service role access tasks" ON tasks
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service role access audit_logs" ON audit_logs
    FOR ALL USING (true) WITH CHECK (true);
