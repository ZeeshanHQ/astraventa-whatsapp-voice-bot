-- Astraventa Multi-Tenant Voice AI Platform Schema
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Tenants Table (Each client/business)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    industry TEXT,
    website_url TEXT,
    phone_number TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Agent Configurations Table (Dynamic prompt, voice, rules per client)
CREATE TABLE IF NOT EXISTS agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Default Voice Agent',
    system_prompt TEXT NOT NULL,
    first_message TEXT NOT NULL,
    voice_id TEXT NOT NULL DEFAULT 'sonic-english-natural',
    voice_provider TEXT NOT NULL DEFAULT 'cartesia',
    llm_model TEXT NOT NULL DEFAULT 'llama-3.3-70b-versatile',
    stt_model TEXT NOT NULL DEFAULT 'nova-3',
    temperature NUMERIC DEFAULT 0.7,
    rules JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Demo / Call Sessions (Tracks browser tests and live prospect calls)
CREATE TABLE IF NOT EXISTS demo_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    room_name TEXT NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'webrtc_browser', -- 'webrtc_browser' or 'sip_phone'
    destination_phone TEXT,
    status TEXT DEFAULT 'initiated',
    duration_seconds INT DEFAULT 0,
    transcript JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Contact Settings (For WhatsApp Human Takeover toggle)
CREATE TABLE IF NOT EXISTS contact_settings (
    wa_id TEXT PRIMARY KEY,
    ai_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    contact_name TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_contact_settings_wa_id ON contact_settings (wa_id);

-- 5. WhatsApp & Call Chat Logs
CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGSERIAL PRIMARY KEY,
    wa_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_logs_wa_id ON chat_logs (wa_id);

-- 6. Knowledge Base Vector Search Table
CREATE TABLE IF NOT EXISTS knowledge_base (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Vector Similarity Search RPC Function
CREATE OR REPLACE FUNCTION match_knowledge_base (
    query_embedding VECTOR(768),
    match_threshold FLOAT,
    match_count INT
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        knowledge_base.id,
        knowledge_base.content,
        knowledge_base.metadata,
        1 - (knowledge_base.embedding <=> query_embedding) AS similarity
    FROM knowledge_base
    WHERE 1 - (knowledge_base.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;
