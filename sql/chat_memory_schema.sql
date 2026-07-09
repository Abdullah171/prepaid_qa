CREATE TABLE IF NOT EXISTS public.ppqa_chat_sessions (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.ppqa_chat_messages (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES public.ppqa_chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    dry_run BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ppqa_chat_sessions_updated_at
    ON public.ppqa_chat_sessions (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_ppqa_chat_messages_session_created_at
    ON public.ppqa_chat_messages (session_id, created_at ASC);
