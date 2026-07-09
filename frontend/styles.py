"""Streamlit CSS for the chat interface."""

APP_CSS = """
<style>
:root {
  --ppqa-border: #d8dee8;
  --ppqa-muted: #667085;
  --ppqa-soft: #f6f8fb;
  --ppqa-ink: #101828;
  --ppqa-accent: #0f766e;
  --ppqa-danger: #b42318;
}

.stApp {
  background: #fbfcfd;
}

[data-testid="stSidebar"] {
  background: #f3f5f8;
  border-right: 1px solid var(--ppqa-border);
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  color: var(--ppqa-ink);
  letter-spacing: 0;
}

.block-container {
  max-width: 1120px;
  padding-top: 1.5rem;
  padding-bottom: 3rem;
}

.ppqa-header {
  border-bottom: 1px solid var(--ppqa-border);
  margin-bottom: 1.25rem;
  padding-bottom: 0.85rem;
}

.ppqa-title {
  color: var(--ppqa-ink);
  font-size: 1.45rem;
  font-weight: 650;
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
  border: 1px dashed var(--ppqa-border);
  background: #ffffff;
  display: flex;
  min-height: 42vh;
  justify-content: center;
  padding: 2rem;
}

.ppqa-empty-inner {
  max-width: 620px;
  text-align: center;
}

.ppqa-empty-title {
  color: var(--ppqa-ink);
  font-size: 1.35rem;
  font-weight: 650;
  margin-bottom: 0.35rem;
}

.ppqa-empty-copy {
  color: var(--ppqa-muted);
  font-size: 0.98rem;
}

.ppqa-session-meta {
  color: var(--ppqa-muted);
  font-size: 0.78rem;
  margin-top: -0.35rem;
  margin-bottom: 0.35rem;
}

.ppqa-chip {
  border: 1px solid var(--ppqa-border);
  color: var(--ppqa-muted);
  display: inline-block;
  font-size: 0.75rem;
  padding: 0.12rem 0.45rem;
}

.ppqa-health-ok {
  color: var(--ppqa-accent);
  font-size: 0.85rem;
  font-weight: 600;
}

.ppqa-health-bad {
  color: var(--ppqa-danger);
  font-size: 0.85rem;
  font-weight: 600;
}

div[data-testid="stChatMessage"] {
  background: #ffffff;
  border: 1px solid var(--ppqa-border);
  border-radius: 8px;
  margin-bottom: 0.75rem;
  padding: 0.35rem 0.55rem;
}

div[data-testid="stChatInput"] {
  border-top: 1px solid var(--ppqa-border);
  padding-top: 0.6rem;
}

.stButton > button {
  border-radius: 6px;
}

[data-testid="stDataFrame"] {
  border: 1px solid var(--ppqa-border);
}
</style>
"""
