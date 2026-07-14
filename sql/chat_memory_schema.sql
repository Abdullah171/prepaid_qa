CREATE MULTISET TABLE DP_EDW_PPF_STG.SC_PPQA_CHAT_SESSIONS
(
    id          CHAR(36) CHARACTER SET Latin NOT NULL,
    TITLE_       VARCHAR(500) CHARACTER SET Unicode
                    NOT NULL DEFAULT 'New chat',
    created_at  TIMESTAMP(6) WITH TIME Zone
                    NOT NULL DEFAULT Current_Timestamp(6),
    updated_at  TIMESTAMP(6) WITH TIME Zone
                    NOT NULL DEFAULT Current_Timestamp(6),

    CONSTRAINT SC_PK_PPQA_CHAT_SESSIONS
        PRIMARY KEY (id)
);





CREATE MULTISET TABLE DP_EDW_PPF_STG.SC_PPQA_CHAT_MESSAGES
(
    id            CHAR(36) CHARACTER SET Latin NOT NULL,
    session_id    CHAR(36) CHARACTER SET Latin NOT NULL,
    message_role  VARCHAR(9) CHARACTER SET Latin CaseSpecific NOT NULL,
    Content       CLOB CHARACTER SET Unicode NOT NULL,
    dry_run       BYTEINT NOT NULL DEFAULT 0,
    metadata      VARCHAR(32000) CHARACTER SET Unicode
                      NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP(6) WITH TIME Zone
                      NOT NULL DEFAULT Current_Timestamp(6),

    CONSTRAINT SC_PK_PPQA_CHAT_MESSAGES
        PRIMARY KEY (id),

    CONSTRAINT SC_FK_PPQA_MESSAGES_SESSION
        FOREIGN KEY (session_id)
        REFERENCES DP_EDW_PPF_STG.SC_PPQA_CHAT_SESSIONS (id),

    CONSTRAINT SC_CK_PPQA_MESSAGE_ROLE
        CHECK (message_role IN ('user', 'assistant')),

    CONSTRAINT SC_CK_PPQA_DRY_RUN
        CHECK (dry_run IN (0, 1))
)
PRIMARY INDEX (session_id);


CREATE INDEX SC_IDX_PPQA_CHAT_SESSIONS_UPDATED_AT
    (updated_at)
ON DP_EDW_PPF_STG.SC_PPQA_CHAT_SESSIONS;




CREATE INDEX SC_IDX_PPQA_CHAT_MESSAGES_SESSION_CREATED
    (session_id, created_at)
ON DP_EDW_PPF_STG.SC_PPQA_CHAT_MESSAGES;