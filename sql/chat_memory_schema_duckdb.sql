CREATE TABLE IF NOT EXISTS SC_PPQA_CHAT_SESSIONS (
    id UUID PRIMARY KEY,
    title VARCHAR NOT NULL DEFAULT 'New chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS SC_PPQA_CHAT_MESSAGES (
    id UUID PRIMARY KEY,
    -- ChatStore validates the session and deletes its messages explicitly. DuckDB
    -- currently prevents updating a referenced session row when a foreign key is
    -- present, including updates that only change updated_at.
    session_id UUID NOT NULL,
    message_role VARCHAR NOT NULL CHECK (message_role IN ('user', 'assistant')),
    content VARCHAR NOT NULL,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSON NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS SC_IDX_PPQA_CHAT_SESSIONS_UPDATED_AT
    ON SC_PPQA_CHAT_SESSIONS (updated_at);

CREATE INDEX IF NOT EXISTS SC_IDX_PPQA_CHAT_MESSAGES_SESSION_CREATED_AT
    ON SC_PPQA_CHAT_MESSAGES (session_id, created_at);
