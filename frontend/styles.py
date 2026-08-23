"""Streamlit CSS for the Prepaid QA chat interface."""

APP_CSS = """
<style>
:root {
  --ppqa-stc-purple: #4f008c;
  --ppqa-purple-bright: #7520a3;
  --ppqa-purple-dark: #2f0054;
  --ppqa-stc-dark: #1d252d;
  --ppqa-cyan: #00c2c7;
  --ppqa-magenta: #ff375e;
  --ppqa-border: #ddd3e4;
  --ppqa-border-strong: #cbbcd7;
  --ppqa-muted: #6c6472;
  --ppqa-soft: #f2edf6;
  --ppqa-soft-purple: #eadff2;
  --ppqa-ink: #251a2d;
  --ppqa-surface: #ffffff;
  --ppqa-danger: #b4233d;
  --ppqa-success: #087b5b;
  --ppqa-shadow-sm: 0 3px 12px rgba(79, 0, 140, 0.07);
  --ppqa-shadow-md: 0 18px 48px rgba(79, 0, 140, 0.11);
}

.stApp {
  background:
    radial-gradient(circle at 88% 2%, rgba(79, 0, 140, 0.12), transparent 27rem),
    radial-gradient(circle at 30% 105%, rgba(0, 194, 199, 0.06), transparent 32rem),
    linear-gradient(180deg, #faf8fb 0%, #f3eef6 100%);
  color: var(--ppqa-ink);
}

.stApp,
.stApp button,
.stApp input,
.stApp textarea {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

header[data-testid="stHeader"] {
  background: rgba(250, 248, 251, 0.86);
  border-bottom: 1px solid rgba(79, 0, 140, 0.06);
  backdrop-filter: blur(14px);
}

[data-testid="stSidebar"] {
  background:
    radial-gradient(circle at 30% 0%, rgba(79, 0, 140, 0.1), transparent 18rem),
    linear-gradient(180deg, #fcfafc 0%, #f2edf6 100%);
  border-right: 1px solid var(--ppqa-border);
  box-shadow: 10px 0 36px rgba(79, 0, 140, 0.06);
}

[data-testid="stCaptionContainer"] p {
  color: var(--ppqa-muted);
}

.stApp a {
  color: var(--ppqa-cyan);
}

[data-testid="stSidebar"] > div:first-child {
  padding-top: 1rem;
}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.7rem;
}

/* Keep chat content readable while Streamlit replaces stale elements during
   a long-running analysis. */
.stMain [data-testid="stElementContainer"][data-stale="true"] {
  opacity: 1 !important;
  transition: none !important;
}

.block-container {
  max-width: 980px;
  padding-top: 1rem;
  padding-bottom: 6rem;
}

.ppqa-brand {
  align-items: center;
  background:
    radial-gradient(circle at 92% 8%, rgba(0, 194, 199, 0.32), transparent 5rem),
    linear-gradient(135deg, var(--ppqa-purple-dark), var(--ppqa-stc-purple));
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 18px;
  box-shadow: 0 14px 34px rgba(79, 0, 140, 0.2);
  display: flex;
  gap: 0.8rem;
  margin: 0.15rem 0 0.65rem;
  min-height: 74px;
  overflow: hidden;
  padding: 0.85rem;
  position: relative;
}

.ppqa-brand::after {
  background: linear-gradient(90deg, var(--ppqa-cyan), var(--ppqa-magenta));
  bottom: 0;
  content: "";
  height: 3px;
  left: 0;
  position: absolute;
  width: 100%;
}

.ppqa-brand-mark {
  align-items: center;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 13px;
  color: #ffffff;
  display: flex;
  flex: 0 0 auto;
  font-size: 0.88rem;
  font-weight: 800;
  height: 44px;
  justify-content: center;
  letter-spacing: -0.02em;
  line-height: 1;
  width: 44px;
}

.ppqa-brand-copy {
  min-width: 0;
}

.ppqa-brand-title {
  color: #ffffff;
  font-size: 1.02rem;
  font-weight: 760;
  line-height: 1.2;
}

.ppqa-brand-subtitle {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.76rem;
  font-weight: 540;
  margin-top: 0.18rem;
}

.ppqa-section-label {
  color: var(--ppqa-muted);
  font-size: 0.73rem;
  font-weight: 760;
  letter-spacing: 0.065em;
  padding-top: 0.35rem;
  text-transform: uppercase;
}

[data-testid="stSidebar"] [data-testid="stToggle"] label {
  color: var(--ppqa-ink);
  font-size: 0.88rem;
}

[data-testid="stSidebar"] hr {
  border-color: var(--ppqa-border);
  margin: 0.25rem 0;
}

.ppqa-health {
  align-items: center;
  background: #f1f8f5;
  border: 1px solid #d6ebe3;
  border-radius: 999px;
  display: inline-flex;
  font-size: 0.76rem;
  font-weight: 680;
  gap: 0.42rem;
  margin-top: 0.15rem;
  padding: 0.3rem 0.58rem;
}

.ppqa-health span,
.ppqa-header-status span {
  background: currentColor;
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(8, 123, 91, 0.11);
  display: inline-block;
  height: 0.42rem;
  width: 0.42rem;
}

.ppqa-health-ok {
  color: var(--ppqa-success);
}

.ppqa-health-bad {
  background: #fff4f5;
  border-color: #f0d4d9;
  color: var(--ppqa-danger);
}

.ppqa-session-meta {
  color: #8a8491;
  font-size: 0.72rem;
  margin: -0.4rem 0 0.15rem;
  padding-left: 0.45rem;
}

.ppqa-header {
  align-items: center;
  border-bottom: 1px solid var(--ppqa-border);
  display: flex;
  justify-content: space-between;
  margin-bottom: 1.25rem;
  min-height: 78px;
  padding: 0.15rem 0 1rem;
}

.ppqa-eyebrow {
  color: var(--ppqa-purple-bright);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
}

.ppqa-title {
  color: var(--ppqa-ink);
  font-size: 1.3rem;
  font-weight: 760;
  letter-spacing: -0.025em;
  line-height: 1.25;
  margin: 0;
}

.ppqa-subtitle {
  color: var(--ppqa-muted);
  font-size: 0.82rem;
  margin-top: 0.18rem;
}

.ppqa-header-status {
  align-items: center;
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border);
  border-radius: 999px;
  box-shadow: var(--ppqa-shadow-sm);
  color: var(--ppqa-success);
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 0.74rem;
  font-weight: 720;
  gap: 0.45rem;
  padding: 0.38rem 0.65rem;
}

.ppqa-empty {
  background:
    radial-gradient(circle at 100% 0%, rgba(79, 0, 140, 0.08), transparent 18rem),
    rgba(255, 255, 255, 0.94);
  border: 1px solid var(--ppqa-border);
  border-radius: 20px;
  box-shadow: var(--ppqa-shadow-md);
  overflow: hidden;
  padding: 1.35rem;
  position: relative;
}

.ppqa-empty::before {
  background: linear-gradient(180deg, var(--ppqa-cyan), var(--ppqa-stc-purple));
  content: "";
  height: 100%;
  left: 0;
  position: absolute;
  top: 0;
  width: 4px;
}

.ppqa-empty-lead {
  align-items: center;
  display: flex;
  gap: 0.9rem;
}

.ppqa-empty-icon {
  align-items: center;
  background: var(--ppqa-soft-purple);
  border: 1px solid #d8c4e5;
  border-radius: 15px;
  display: flex;
  flex: 0 0 auto;
  height: 48px;
  justify-content: center;
  position: relative;
  width: 48px;
}

.ppqa-empty-icon::before,
.ppqa-empty-icon::after,
.ppqa-empty-icon span {
  background: var(--ppqa-purple-bright);
  border-radius: 999px;
  content: "";
  position: absolute;
}

.ppqa-empty-icon::before {
  height: 19px;
  width: 5px;
}

.ppqa-empty-icon::after {
  height: 5px;
  width: 19px;
}

.ppqa-empty-icon span {
  background: var(--ppqa-cyan);
  height: 6px;
  right: 8px;
  top: 8px;
  width: 6px;
}

.ppqa-empty-kicker {
  color: var(--ppqa-purple-bright);
  font-size: 0.72rem;
  font-weight: 780;
  letter-spacing: 0.035em;
  margin-bottom: 0.18rem;
  text-transform: uppercase;
}

.ppqa-empty-title {
  color: var(--ppqa-ink);
  font-size: 1.18rem;
  font-weight: 750;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.ppqa-empty-copy {
  color: var(--ppqa-muted);
  font-size: 0.88rem;
  line-height: 1.55;
  margin-top: 0.2rem;
}

.ppqa-topics {
  display: grid;
  gap: 0.65rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 1.15rem;
}

.ppqa-topic {
  align-items: center;
  background: var(--ppqa-soft);
  border: 1px solid #e8dfed;
  border-radius: 13px;
  display: flex;
  gap: 0.65rem;
  min-width: 0;
  padding: 0.72rem;
}

.ppqa-topic-dot {
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgba(79, 0, 140, 0.07);
  flex: 0 0 auto;
  height: 0.5rem;
  width: 0.5rem;
}

.ppqa-topic-purple { background: var(--ppqa-purple-bright); }
.ppqa-topic-cyan { background: var(--ppqa-cyan); }
.ppqa-topic-magenta { background: var(--ppqa-magenta); }

.ppqa-topic strong,
.ppqa-topic small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ppqa-topic strong {
  color: var(--ppqa-ink);
  font-size: 0.8rem;
  font-weight: 720;
}

.ppqa-topic small {
  color: var(--ppqa-muted);
  font-size: 0.7rem;
  margin-top: 0.12rem;
}

.ppqa-empty-hint {
  border-top: 1px solid var(--ppqa-border);
  color: var(--ppqa-muted);
  font-size: 0.8rem;
  line-height: 1.45;
  margin-top: 1rem;
  padding-top: 0.85rem;
}

.ppqa-empty-hint span {
  background: var(--ppqa-soft-purple);
  border-radius: 999px;
  color: var(--ppqa-purple-bright);
  font-size: 0.68rem;
  font-weight: 760;
  margin-right: 0.35rem;
  padding: 0.22rem 0.48rem;
  text-transform: uppercase;
}

div[data-testid="stChatMessage"] {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid var(--ppqa-border);
  border-radius: 18px;
  box-shadow: var(--ppqa-shadow-sm);
  margin-bottom: 0.72rem;
  padding: 0.65rem 0.8rem;
}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: linear-gradient(135deg, #f3eaf8, #faf7fc);
  border-color: #ddc9e8;
}

[data-testid="stChatMessageAvatarUser"] {
  background: var(--ppqa-stc-purple);
  color: #ffffff;
}

[data-testid="stChatMessageAvatarAssistant"] {
  background: #e5f7f7;
  color: #007b80;
}

div[data-testid="stChatInput"] {
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border-strong);
  border-radius: 18px;
  box-shadow: 0 14px 38px rgba(79, 0, 140, 0.15);
  overflow: hidden;
}

div[data-testid="stChatInput"]:focus-within {
  border-color: rgba(79, 0, 140, 0.55);
  box-shadow: 0 0 0 3px rgba(79, 0, 140, 0.09), 0 14px 38px rgba(79, 0, 140, 0.15);
}

div[data-testid="stChatInput"] textarea::placeholder {
  color: #8c8492;
}

div[data-testid="stChatInput"] textarea {
  color: var(--ppqa-ink);
  caret-color: var(--ppqa-cyan);
}

[data-testid="stBottom"] > div {
  background: linear-gradient(180deg, transparent, rgba(243, 238, 246, 0.97) 34%);
  padding-top: 1.4rem;
}

/* During generation, replace the composer's send arrow with a compact stop
   control in the same position. */
.st-key-active-composer {
  position: relative;
}

.st-key-active-composer [data-testid="stChatInput"] button {
  visibility: hidden;
}

.st-key-active-composer .st-key-stop-analysis {
  bottom: 0.58rem;
  position: absolute;
  right: 0.72rem;
  width: 2.15rem;
  z-index: 10;
}

.st-key-active-composer .stButton {
  width: 2.15rem;
}

.st-key-active-composer .stButton > button {
  align-items: center;
  border-radius: 999px;
  display: flex;
  height: 2.15rem;
  justify-content: center;
  min-height: 2.15rem;
  padding: 0;
  width: 2.15rem;
}

.st-key-active-composer .stButton [data-testid="stMarkdownContainer"] {
  border: 0;
  clip: rect(0 0 0 0);
  height: 1px;
  margin: -1px;
  overflow: hidden;
  padding: 0;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}

.stButton > button {
  background: var(--ppqa-soft);
  border-color: var(--ppqa-border-strong);
  border-radius: 10px;
  color: var(--ppqa-ink);
  font-weight: 650;
  letter-spacing: 0;
  transition: border-color 150ms ease, box-shadow 150ms ease, color 150ms ease, transform 150ms ease;
}

.stButton > button:hover {
  background: #ece3f2;
  border-color: rgba(79, 0, 140, 0.5);
  box-shadow: var(--ppqa-shadow-sm);
  color: var(--ppqa-purple-bright);
  transform: translateY(-1px);
}

.stButton > button:focus-visible,
.stTextInput input:focus-visible,
.stTextArea textarea:focus-visible {
  outline: 3px solid rgba(79, 0, 140, 0.16);
  outline-offset: 2px;
}

.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--ppqa-stc-purple), #6810a5);
  border-color: var(--ppqa-stc-purple);
  box-shadow: 0 6px 16px rgba(79, 0, 140, 0.18);
  color: #ffffff;
}

.stButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #420076, #5c0795);
  border-color: #420076;
  color: #ffffff;
}

.stButton > button[kind="tertiary"] {
  background: transparent;
  border-color: transparent;
}

[data-testid="stSidebar"] .stButton > button {
  font-size: 0.82rem;
  min-height: 2.35rem;
}

@keyframes ppqa-thinking-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.ppqa-non-thinking-progress {
  align-items: center;
  color: var(--ppqa-muted);
  display: inline-flex;
  font-size: 0.86rem;
  gap: 0.65rem;
  min-height: 2.25rem;
}

.ppqa-progress-spinner {
  animation: ppqa-thinking-spin 700ms linear infinite;
  border: 2px solid rgba(79, 0, 140, 0.18);
  border-radius: 50%;
  border-top-color: var(--ppqa-stc-purple);
  box-sizing: border-box;
  display: inline-block;
  flex: 0 0 auto;
  height: 1.15rem;
  width: 1.15rem;
  will-change: transform;
}

/* Stable live-reasoning control. The spinner is CSS-only, so polling reruns do
   not restart it or switch it between status icons. */
.st-key-live-thinking .stButton > button {
  align-items: center;
  background: linear-gradient(135deg, #ffffff 0%, #eee5f4 100%);
  border: 1px solid rgba(79, 0, 140, 0.2);
  border-radius: 999px;
  box-shadow: 0 3px 12px rgba(79, 0, 140, 0.08);
  color: var(--ppqa-purple-bright);
  display: inline-flex;
  font-size: 0.86rem;
  gap: 0.55rem;
  min-height: 2.25rem;
  padding: 0.35rem 0.78rem;
}

.st-key-live-thinking [data-testid="stIconMaterial"] {
  animation: ppqa-thinking-spin 700ms linear infinite !important;
  display: inline-flex !important;
  transform-origin: 50% 50% !important;
  will-change: transform;
}

.st-key-live-thinking-content {
  background: linear-gradient(180deg, #ffffff 0%, #f7f2f9 100%);
  border-radius: 12px;
  margin-top: 0.2rem;
}

.stTextInput input,
.stTextArea textarea {
  background: var(--ppqa-soft);
  border-color: var(--ppqa-border-strong);
  border-radius: 10px;
  color: var(--ppqa-ink);
}

[data-testid="stMetric"] {
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border);
  border-radius: 14px;
  box-shadow: var(--ppqa-shadow-sm);
  padding: 0.75rem 0.85rem;
}

[data-testid="stMetricLabel"] {
  color: var(--ppqa-muted);
}

[data-testid="stMetricValue"] {
  color: var(--ppqa-cyan);
}

[data-testid="stDataFrame"] {
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border);
  border-radius: 14px;
  overflow: hidden;
}

div[data-testid="stExpander"] {
  background: rgba(255, 255, 255, 0.88);
  border-color: var(--ppqa-border);
  border-radius: 14px;
}

@media (max-width: 720px) {
  .block-container {
    padding-top: 0.65rem;
  }

  .ppqa-header {
    min-height: 68px;
  }

  .ppqa-header-status {
    display: none;
  }

  .ppqa-topics {
    grid-template-columns: 1fr;
  }

  .ppqa-empty {
    border-radius: 16px;
    padding: 1.1rem;
  }

  .ppqa-empty-lead {
    align-items: flex-start;
  }

  .ppqa-empty-icon {
    height: 42px;
    width: 42px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }

  .ppqa-progress-spinner,
  .st-key-live-thinking [data-testid="stIconMaterial"] {
    animation-duration: 1.4s !important;
  }
}
</style>
"""
