"""Streamlit CSS for the chat interface."""

APP_CSS = """
<style>
:root {
  --ppqa-stc-purple: #4f008c;
  --ppqa-stc-dark: #1d252d;
  --ppqa-cyan: #00c2c7;
  --ppqa-magenta: #ff375e;
  --ppqa-border: #d9dee7;
  --ppqa-muted: #5b667a;
  --ppqa-soft: #f6f7fa;
  --ppqa-ink: #18212f;
  --ppqa-surface: #ffffff;
  --ppqa-accent: var(--ppqa-stc-purple);
  --ppqa-danger: #b42318;
  --ppqa-success: #007a5a;
}

.stApp {
  background: #f7f8fb;
  color: var(--ppqa-ink);
}

[data-testid="stSidebar"] {
  background: var(--ppqa-surface);
  border-right: 1px solid var(--ppqa-border);
  box-shadow: 8px 0 20px rgba(29, 37, 45, 0.035);
}

/* Long-running work is communicated by st.status. Keep already-rendered chat
   content readable while Streamlit replaces stale elements during a rerun. */
.stMain [data-testid="stElementContainer"][data-stale="true"] {
  opacity: 1 !important;
  transition: none !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  color: var(--ppqa-stc-dark);
  letter-spacing: 0;
}

.block-container {
  max-width: 1120px;
  padding-top: 1.35rem;
  padding-bottom: 3rem;
}

.ppqa-brand {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  margin: 0.2rem 0 1.15rem;
}

.ppqa-brand-mark {
  align-items: center;
  background: var(--ppqa-stc-purple);
  border-radius: 8px;
  color: #ffffff;
  display: flex;
  font-size: 1rem;
  font-weight: 800;
  height: 44px;
  justify-content: center;
  letter-spacing: 0;
  line-height: 1;
  width: 44px;
}

.ppqa-brand-title {
  color: var(--ppqa-stc-dark);
  font-size: 0.98rem;
  font-weight: 750;
  line-height: 1.2;
}

.ppqa-brand-subtitle {
  color: var(--ppqa-muted);
  font-size: 0.78rem;
  font-weight: 550;
  margin-top: 0.12rem;
}

.ppqa-header {
  border-bottom: 1px solid var(--ppqa-border);
  margin-bottom: 1.15rem;
  padding-bottom: 0.9rem;
  position: relative;
}

.ppqa-header::after {
  background: linear-gradient(
    90deg,
    var(--ppqa-stc-purple),
    var(--ppqa-cyan),
    var(--ppqa-magenta)
  );
  bottom: -1px;
  content: "";
  height: 3px;
  left: 0;
  position: absolute;
  width: 104px;
}

.ppqa-title {
  color: var(--ppqa-stc-dark);
  font-size: 1.42rem;
  font-weight: 750;
  line-height: 1.25;
  margin: 0;
}

.ppqa-subtitle {
  color: var(--ppqa-muted);
  font-size: 0.9rem;
  margin-top: 0.25rem;
}

.ppqa-empty {
  align-items: center;
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(29, 37, 45, 0.05);
  display: flex;
  min-height: 46vh;
  justify-content: flex-start;
  padding: 2rem;
}

.ppqa-empty-inner {
  border-left: 4px solid var(--ppqa-stc-purple);
  max-width: 620px;
  padding-left: 1.25rem;
  text-align: left;
}

.ppqa-empty-kicker {
  color: var(--ppqa-stc-purple);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  margin-bottom: 0.35rem;
  text-transform: uppercase;
}

.ppqa-empty-title {
  color: var(--ppqa-stc-dark);
  font-size: 1.42rem;
  font-weight: 760;
  margin-bottom: 0.35rem;
}

.ppqa-empty-copy {
  color: var(--ppqa-muted);
  font-size: 0.98rem;
}

.ppqa-session-meta {
  color: var(--ppqa-muted);
  font-size: 0.82rem;
  margin-top: -0.28rem;
  margin-bottom: 0.42rem;
  padding-left: 0.12rem;
}

.ppqa-chip {
  border: 1px solid var(--ppqa-border);
  color: var(--ppqa-muted);
  display: inline-block;
  font-size: 0.75rem;
  padding: 0.12rem 0.45rem;
}

.ppqa-health-ok {
  color: var(--ppqa-success);
  font-size: 0.85rem;
  font-weight: 700;
}

.ppqa-health-bad {
  color: var(--ppqa-danger);
  font-size: 0.85rem;
  font-weight: 600;
}

div[data-testid="stChatMessage"] {
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border);
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(29, 37, 45, 0.04);
  margin-bottom: 0.72rem;
  padding: 0.42rem 0.62rem;
}

div[data-testid="stChatInput"] {
  border-top: 0;
  padding-top: 0.45rem;
}

.stButton > button {
  border-radius: 6px;
  border-color: var(--ppqa-border);
  color: var(--ppqa-stc-dark);
  font-weight: 650;
  letter-spacing: 0;
}

.stButton > button:hover {
  border-color: var(--ppqa-stc-purple);
  color: var(--ppqa-stc-purple);
}

.stButton > button:focus-visible,
.stTextInput input:focus-visible,
.stTextArea textarea:focus-visible {
  outline: 3px solid rgba(79, 0, 140, 0.22);
  outline-offset: 2px;
}

.stButton > button[kind="primary"] {
  background: var(--ppqa-stc-purple);
  border-color: var(--ppqa-stc-purple);
  color: #ffffff;
}

.stButton > button[kind="primary"]:hover {
  background: #3f0070;
  border-color: #3f0070;
  color: #ffffff;
}

@keyframes ppqa-thinking-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Stable live-reasoning control. The spinner is CSS-only, so polling reruns do
   not restart it or switch it between status icons. */
.st-key-live-thinking .stButton > button {
  align-items: center;
  background: linear-gradient(135deg, #ffffff 0%, #f6f0fb 100%);
  border: 1px solid rgba(79, 0, 140, 0.2);
  border-radius: 999px;
  box-shadow: 0 3px 12px rgba(79, 0, 140, 0.08);
  color: var(--ppqa-stc-purple);
  display: inline-flex;
  font-size: 0.86rem;
  gap: 0.55rem;
  min-height: 2.25rem;
  padding: 0.35rem 0.78rem;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.st-key-live-thinking [data-testid="stIconMaterial"] {
  animation: ppqa-thinking-spin 700ms linear infinite !important;
  display: inline-flex !important;
  transform-origin: 50% 50% !important;
  will-change: transform;
}

.st-key-live-thinking .stButton > button:hover {
  background: #ffffff;
  border-color: rgba(79, 0, 140, 0.48);
  box-shadow: 0 5px 16px rgba(79, 0, 140, 0.14);
  color: var(--ppqa-stc-purple);
  transform: translateY(-1px);
}

.st-key-live-thinking-content {
  background: linear-gradient(180deg, #ffffff 0%, #fbf9fd 100%);
  border-radius: 8px;
  margin-top: 0.2rem;
}

.stTextInput input,
.stTextArea textarea {
  border-radius: 6px;
}

[data-testid="stMetric"] {
  background: var(--ppqa-soft);
  border: 1px solid var(--ppqa-border);
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
}

[data-testid="stDataFrame"] {
  border: 1px solid var(--ppqa-border);
  border-radius: 8px;
  overflow: hidden;
}

div[data-testid="stExpander"] {
  border-color: var(--ppqa-border);
  border-radius: 8px;
}

@media (max-width: 720px) {
  .block-container {
    padding-top: 0.8rem;
  }

  .ppqa-empty {
    min-height: 30vh;
    padding: 1.25rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
"""
