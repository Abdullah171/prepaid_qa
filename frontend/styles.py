"""Streamlit CSS for the Prepaid QA chat interface."""

APP_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════════════
   Prepaid QA – Design Tokens
   ═══════════════════════════════════════════════════════════════════════ */
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

/* ═══════════════════════════════════════════════════════════════════════
   Global light-mode overrides
   Streamlit injects Emotion-generated classes + CSS vars for theming.
   We force everything to light-mode here so the dark theme never leaks.
   ═══════════════════════════════════════════════════════════════════════ */
.stApp {
  --background-color: #faf8fb !important;
  --secondary-background-color: #f2edf6 !important;
  --text-color: #251a2d !important;
  --primary-color: #4f008c !important;
  color-scheme: light !important;
}

.stApp,
.stApp p,
.stApp h1, .stApp h2, .stApp h3,
.stApp h4, .stApp h5, .stApp h6,
.stApp li,
.stApp label {
  color: var(--ppqa-ink) !important;
}

/* Spans except code tokens and data-testid elements */
.stApp span:not([class*="token"]):not([data-testid]):not(.st-emotion-cache-1gulkj5) {
  color: var(--ppqa-ink) !important;
}

/* ── App background ── */
.stApp {
  background:
    radial-gradient(circle at 88% 2%, rgba(79, 0, 140, 0.12), transparent 27rem),
    radial-gradient(circle at 30% 105%, rgba(0, 194, 199, 0.06), transparent 32rem),
    linear-gradient(180deg, #faf8fb 0%, #f3eef6 100%) !important;
}

.stApp,
.stApp button,
.stApp input,
.stApp textarea {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* ── Header ── */
header[data-testid="stHeader"] {
  background: rgba(250, 248, 251, 0.86) !important;
  border-bottom: 1px solid rgba(79, 0, 140, 0.06) !important;
  backdrop-filter: blur(14px);
}

/* ═══════════════════════════════════════════════════════════════════════
   Sidebar
   ═══════════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebar"] > div > div,
[data-testid="stSidebar"] > div > div > div {
  background:
    radial-gradient(circle at 30% 0%, rgba(79, 0, 140, 0.1), transparent 18rem),
    linear-gradient(180deg, #fcfafc 0%, #f2edf6 100%) !important;
  border-right: 1px solid var(--ppqa-border) !important;
}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"],
[data-testid="stSidebar"] [data-testid="stElementContainer"],
[data-testid="stSidebar"] section {
  background: transparent !important;
}

[data-testid="stSidebar"] > div:first-child {
  padding-top: 1rem;
  box-shadow: 10px 0 36px rgba(79, 0, 140, 0.06);
}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.7rem;
}

[data-testid="stCaptionContainer"] p {
  color: var(--ppqa-muted) !important;
}

.stApp a {
  color: var(--ppqa-cyan) !important;
}

[data-testid="stSidebar"] hr {
  border-color: var(--ppqa-border);
  margin: 0.25rem 0;
}

/* ── Toggle switches: visible purple tracks & clear labels ── */
[data-testid="stSidebar"] [data-testid="stToggle"] label,
[data-testid="stSidebar"] [data-testid="stToggle"] label p,
[data-testid="stSidebar"] [data-testid="stToggle"] label span {
  color: var(--ppqa-ink) !important;
  font-size: 0.88rem;
}

/* Toggle track – unchecked: soft purple, checked: solid purple */
[data-testid="stToggle"] > div > div > label > div:first-of-type {
  background-color: #d4c4e0 !important;
  border: none !important;
  opacity: 1 !important;
}

[data-testid="stToggle"] > div > div > label > div:first-of-type:has(input:checked) {
  background-color: var(--ppqa-stc-purple) !important;
}

/* Alternative approach: target the actual input + sibling */
.stApp [data-testid="stToggle"] input[type="checkbox"] + div,
.stApp [data-testid="stToggle"] input[type="checkbox"] ~ div[role] {
  background-color: #d4c4e0 !important;
}

.stApp [data-testid="stToggle"] input[type="checkbox"]:checked + div,
.stApp [data-testid="stToggle"] input[type="checkbox"]:checked ~ div[role] {
  background-color: var(--ppqa-stc-purple) !important;
}

/* Toggle thumb */
.stApp [data-testid="stToggle"] input[type="checkbox"] + div::before,
.stApp [data-testid="stToggle"] input[type="checkbox"] ~ div[role]::before {
  background-color: #ffffff !important;
}

/* Help icon next to toggles */
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg {
  color: var(--ppqa-muted) !important;
  fill: var(--ppqa-muted) !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   Brand card (sidebar header)
   ═══════════════════════════════════════════════════════════════════════ */
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
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 13px;
  color: #ffffff !important;
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

.ppqa-brand-mark,
.ppqa-brand-mark span {
  color: #ffffff !important;
}

.ppqa-brand-copy {
  min-width: 0;
}

.ppqa-brand-title,
.ppqa-brand-title span {
  color: #ffffff !important;
  font-size: 1.02rem;
  font-weight: 760;
  line-height: 1.2;
}

.ppqa-brand-subtitle,
.ppqa-brand-subtitle span {
  color: rgba(255, 255, 255, 0.85) !important;
  font-size: 0.76rem;
  font-weight: 540;
  margin-top: 0.18rem;
}

/* ── Section label ── */
.ppqa-section-label {
  color: var(--ppqa-muted) !important;
  font-size: 0.73rem;
  font-weight: 760;
  letter-spacing: 0.065em;
  padding-top: 0.35rem;
  text-transform: uppercase;
}

/* ═══════════════════════════════════════════════════════════════════════
   Health badge
   ═══════════════════════════════════════════════════════════════════════ */
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
  background: currentColor !important;
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(8, 123, 91, 0.11);
  color: inherit !important;
  display: inline-block;
  height: 0.42rem;
  width: 0.42rem;
}

.ppqa-health-ok,
.ppqa-health-ok span {
  color: var(--ppqa-success) !important;
}

.ppqa-health-bad {
  background: #fff4f5 !important;
  border-color: #f0d4d9;
  color: var(--ppqa-danger) !important;
}

.ppqa-health-bad span {
  color: var(--ppqa-danger) !important;
  box-shadow: 0 0 0 3px rgba(180, 35, 61, 0.11);
}

/* ── Session meta ── */
.ppqa-session-meta {
  color: #8a8491 !important;
  font-size: 0.72rem;
  margin: -0.4rem 0 0.15rem;
  padding-left: 0.45rem;
}

/* ═══════════════════════════════════════════════════════════════════════
   Page header
   ═══════════════════════════════════════════════════════════════════════ */
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
  color: var(--ppqa-purple-bright) !important;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
}

.ppqa-title {
  color: var(--ppqa-ink) !important;
  font-size: 1.3rem;
  font-weight: 760;
  letter-spacing: -0.025em;
  line-height: 1.25;
  margin: 0;
}

.ppqa-subtitle {
  color: var(--ppqa-muted) !important;
  font-size: 0.82rem;
  margin-top: 0.18rem;
}

.ppqa-header-status {
  align-items: center;
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border);
  border-radius: 999px;
  box-shadow: var(--ppqa-shadow-sm);
  color: var(--ppqa-success) !important;
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 0.74rem;
  font-weight: 720;
  gap: 0.45rem;
  padding: 0.38rem 0.65rem;
}

/* ═══════════════════════════════════════════════════════════════════════
   Empty state
   ═══════════════════════════════════════════════════════════════════════ */
.ppqa-empty {
  background:
    radial-gradient(circle at 100% 0%, rgba(79, 0, 140, 0.08), transparent 18rem),
    rgba(255, 255, 255, 0.94) !important;
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
  background: var(--ppqa-purple-bright) !important;
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
  background: var(--ppqa-cyan) !important;
  height: 6px;
  right: 8px;
  top: 8px;
  width: 6px;
}

.ppqa-empty-kicker {
  color: var(--ppqa-purple-bright) !important;
  font-size: 0.72rem;
  font-weight: 780;
  letter-spacing: 0.035em;
  margin-bottom: 0.18rem;
  text-transform: uppercase;
}

.ppqa-empty-title {
  color: var(--ppqa-ink) !important;
  font-size: 1.18rem;
  font-weight: 750;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.ppqa-empty-copy {
  color: var(--ppqa-muted) !important;
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
  background: var(--ppqa-soft) !important;
  border: 1px solid #e8dfed !important;
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

.ppqa-topic-purple { background: var(--ppqa-purple-bright) !important; }
.ppqa-topic-cyan { background: var(--ppqa-cyan) !important; }
.ppqa-topic-magenta { background: var(--ppqa-magenta) !important; }

.ppqa-topic strong,
.ppqa-topic small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ppqa-topic strong {
  color: var(--ppqa-ink) !important;
  font-size: 0.8rem;
  font-weight: 720;
}

.ppqa-topic small {
  color: var(--ppqa-muted) !important;
  font-size: 0.7rem;
  margin-top: 0.12rem;
}

.ppqa-empty-hint {
  border-top: 1px solid var(--ppqa-border);
  color: var(--ppqa-muted) !important;
  font-size: 0.8rem;
  line-height: 1.45;
  margin-top: 1rem;
  padding-top: 0.85rem;
}

.ppqa-empty-hint span {
  background: var(--ppqa-soft-purple) !important;
  border-radius: 999px;
  color: var(--ppqa-purple-bright) !important;
  font-size: 0.68rem;
  font-weight: 760;
  margin-right: 0.35rem;
  padding: 0.22rem 0.48rem;
  text-transform: uppercase;
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

/* ═══════════════════════════════════════════════════════════════════════
   Chat messages
   ═══════════════════════════════════════════════════════════════════════ */
div[data-testid="stChatMessage"] {
  background: rgba(255, 255, 255, 0.96) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 18px;
  box-shadow: var(--ppqa-shadow-sm);
  margin-bottom: 0.72rem;
  padding: 0.65rem 0.8rem;
}

div[data-testid="stChatMessage"] p,
div[data-testid="stChatMessage"] span:not([class*="token"]),
div[data-testid="stChatMessage"] div:not([data-testid]) {
  color: var(--ppqa-ink) !important;
}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: linear-gradient(135deg, #f3eaf8, #faf7fc) !important;
  border-color: #ddc9e8 !important;
}

/* ── User avatar: purple background, white icon ── */
[data-testid="stChatMessageAvatarUser"],
.stApp [data-testid="stChatMessageAvatarUser"] {
  background: linear-gradient(135deg, var(--ppqa-stc-purple), var(--ppqa-purple-bright)) !important;
  border: none !important;
  border-radius: 12px !important;
}

.stApp [data-testid="stChatMessageAvatarUser"] *,
[data-testid="stChatMessageAvatarUser"] svg,
[data-testid="stChatMessageAvatarUser"] span,
[data-testid="stChatMessageAvatarUser"] [data-testid="stIconMaterial"] {
  color: #ffffff !important;
  fill: #ffffff !important;
}

/* ── Assistant avatar: teal background, teal-dark icon ── */
[data-testid="stChatMessageAvatarAssistant"],
.stApp [data-testid="stChatMessageAvatarAssistant"] {
  background: linear-gradient(135deg, #d4f0f0, #e5f7f7) !important;
  border: none !important;
  border-radius: 12px !important;
}

.stApp [data-testid="stChatMessageAvatarAssistant"] *,
[data-testid="stChatMessageAvatarAssistant"] svg,
[data-testid="stChatMessageAvatarAssistant"] span,
[data-testid="stChatMessageAvatarAssistant"] [data-testid="stIconMaterial"] {
  color: #007b80 !important;
  fill: #007b80 !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   Chat input box
   ═══════════════════════════════════════════════════════════════════════ */
div[data-testid="stChatInput"],
div[data-testid="stChatInput"] > *,
div[data-testid="stChatInput"] > * > *,
div[data-testid="stChatInput"] > * > * > * {
  background-color: var(--ppqa-surface) !important;
  background: var(--ppqa-surface) !important;
}

div[data-testid="stChatInput"] {
  border: 1px solid var(--ppqa-border-strong) !important;
  border-radius: 18px !important;
  box-shadow: 0 14px 38px rgba(79, 0, 140, 0.15);
  overflow: hidden;
}

div[data-testid="stChatInput"]:focus-within {
  border-color: rgba(79, 0, 140, 0.55) !important;
  box-shadow: 0 0 0 3px rgba(79, 0, 140, 0.09), 0 14px 38px rgba(79, 0, 140, 0.15);
}

div[data-testid="stChatInput"] textarea {
  background: transparent !important;
  background-color: transparent !important;
  color: var(--ppqa-ink) !important;
  caret-color: var(--ppqa-cyan) !important;
}

div[data-testid="stChatInput"] textarea::placeholder {
  color: #8c8492 !important;
}

/* Send button inside chat input */
div[data-testid="stChatInput"] button {
  background: linear-gradient(135deg, var(--ppqa-stc-purple), var(--ppqa-purple-bright)) !important;
  border: none !important;
  border-radius: 12px !important;
  color: #ffffff !important;
}

div[data-testid="stChatInput"] button svg,
div[data-testid="stChatInput"] button span {
  fill: #ffffff !important;
  color: #ffffff !important;
}

div[data-testid="stChatInput"] button:hover {
  background: linear-gradient(135deg, var(--ppqa-purple-bright), #8c3ab8) !important;
}

/* ── Bottom fade ── */
[data-testid="stBottom"] > div {
  background: linear-gradient(180deg, transparent, rgba(243, 238, 246, 0.97) 34%) !important;
  padding-top: 1.4rem;
}

/* ═══════════════════════════════════════════════════════════════════════
   Active analysis stop control
   ═══════════════════════════════════════════════════════════════════════ */
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

/* ═══════════════════════════════════════════════════════════════════════
   Buttons – global defaults
   ═══════════════════════════════════════════════════════════════════════ */
.stApp .stButton > button {
  background: var(--ppqa-soft) !important;
  border: 1px solid var(--ppqa-border-strong) !important;
  border-radius: 10px;
  color: var(--ppqa-ink) !important;
  font-weight: 650;
  letter-spacing: 0;
  transition: border-color 150ms ease, box-shadow 150ms ease, color 150ms ease, transform 150ms ease;
}

.stApp .stButton > button p,
.stApp .stButton > button span,
.stApp .stButton > button div {
  color: var(--ppqa-ink) !important;
}

.stApp .stButton > button:hover {
  background: #ece3f2 !important;
  border-color: rgba(79, 0, 140, 0.5) !important;
  box-shadow: var(--ppqa-shadow-sm);
  color: var(--ppqa-purple-bright) !important;
  transform: translateY(-1px);
}

.stApp .stButton > button:hover p,
.stApp .stButton > button:hover span {
  color: var(--ppqa-purple-bright) !important;
}

/* Focus ring */
.stApp .stButton > button:focus-visible,
.stApp .stTextInput input:focus-visible,
.stApp .stTextArea textarea:focus-visible {
  outline: 3px solid rgba(79, 0, 140, 0.16) !important;
  outline-offset: 2px;
}

/* ── Primary buttons: purple gradient, white text ── */
.stApp .stButton > button[kind="primary"],
.stApp .stButton > button[data-testid="stBaseButton-primary"],
.stApp button[kind="primary"] {
  background: linear-gradient(135deg, var(--ppqa-stc-purple), #6810a5) !important;
  border: 1px solid var(--ppqa-stc-purple) !important;
  box-shadow: 0 6px 16px rgba(79, 0, 140, 0.18);
  color: #ffffff !important;
}

.stApp .stButton > button[kind="primary"]:hover,
.stApp .stButton > button[data-testid="stBaseButton-primary"]:hover,
.stApp button[kind="primary"]:hover {
  background: linear-gradient(135deg, #420076, #5c0795) !important;
  border-color: #420076 !important;
  color: #ffffff !important;
}

.stApp .stButton > button[kind="primary"] *,
.stApp .stButton > button[data-testid="stBaseButton-primary"] *,
.stApp button[kind="primary"] p,
.stApp button[kind="primary"] span,
.stApp button[kind="primary"] div,
.stApp button[kind="primary"] [data-testid="stIconMaterial"] {
  color: #ffffff !important;
}

/* ── Tertiary buttons ── */
.stApp .stButton > button[kind="tertiary"],
.stApp .stButton > button[data-testid="stBaseButton-tertiary"] {
  background: transparent !important;
  border-color: transparent !important;
}

.stApp .stButton > button[kind="tertiary"] p,
.stApp .stButton > button[kind="tertiary"] span,
.stApp .stButton > button[data-testid="stBaseButton-tertiary"] p,
.stApp .stButton > button[data-testid="stBaseButton-tertiary"] span {
  color: var(--ppqa-purple-bright) !important;
}

.stApp .stButton > button[kind="tertiary"]:hover,
.stApp .stButton > button[data-testid="stBaseButton-tertiary"]:hover {
  background: rgba(79, 0, 140, 0.06) !important;
  transform: none;
}

/* ═══════════════════════════════════════════════════════════════════════
   Sidebar buttons – session history
   ═══════════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] .stApp .stButton > button,
.stApp [data-testid="stSidebar"] .stButton > button {
  background: rgba(255, 255, 255, 0.7) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 10px;
  font-size: 0.82rem;
  min-height: 2.35rem;
}

[data-testid="stSidebar"] .stApp .stButton > button:hover,
.stApp [data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(255, 255, 255, 0.95) !important;
  border-color: rgba(79, 0, 140, 0.4) !important;
}

/* Active session in sidebar: purple, NOT red */
.stApp [data-testid="stSidebar"] .stButton > button[kind="primary"],
.stApp [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"],
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"],
[data-testid="stSidebar"] button[kind="primary"] {
  background: linear-gradient(135deg, var(--ppqa-stc-purple), #6810a5) !important;
  border: 1px solid var(--ppqa-stc-purple) !important;
  box-shadow: 0 6px 16px rgba(79, 0, 140, 0.18);
  color: #ffffff !important;
}

.stApp [data-testid="stSidebar"] .stButton > button[kind="primary"] *,
.stApp [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] *,
[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
[data-testid="stSidebar"] .stButton > button[kind="primary"] span,
[data-testid="stSidebar"] .stButton > button[kind="primary"] [data-testid="stIconMaterial"],
[data-testid="stSidebar"] button[kind="primary"] span,
[data-testid="stSidebar"] button[kind="primary"] p {
  color: #ffffff !important;
}

/* Sidebar tertiary (delete, refresh) */
.stApp [data-testid="stSidebar"] .stButton > button[kind="tertiary"],
.stApp [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-tertiary"],
[data-testid="stSidebar"] .stButton > button[kind="tertiary"] {
  background: transparent !important;
  border-color: transparent !important;
}

.stApp [data-testid="stSidebar"] .stButton > button[kind="tertiary"]:hover,
[data-testid="stSidebar"] .stButton > button[kind="tertiary"]:hover {
  background: rgba(79, 0, 140, 0.06) !important;
  transform: none;
}

/* Material icons in sidebar */
.stApp [data-testid="stSidebar"] [data-testid="stIconMaterial"] {
  color: var(--ppqa-ink) !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   Thinking / progress
   ═══════════════════════════════════════════════════════════════════════ */
@keyframes ppqa-thinking-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.ppqa-non-thinking-progress {
  align-items: center;
  color: var(--ppqa-muted) !important;
  display: inline-flex;
  font-size: 0.86rem;
  gap: 0.65rem;
  min-height: 2.25rem;
}

.ppqa-progress-spinner {
  animation: ppqa-thinking-spin 700ms linear infinite;
  border: 2px solid rgba(79, 0, 140, 0.18) !important;
  border-radius: 50%;
  border-top-color: var(--ppqa-stc-purple) !important;
  box-sizing: border-box;
  display: inline-block;
  flex: 0 0 auto;
  height: 1.15rem;
  width: 1.15rem;
  will-change: transform;
}

.st-key-live-thinking .stButton > button {
  align-items: center;
  background: linear-gradient(135deg, #ffffff 0%, #eee5f4 100%) !important;
  border: 1px solid rgba(79, 0, 140, 0.2) !important;
  border-radius: 999px;
  box-shadow: 0 3px 12px rgba(79, 0, 140, 0.08);
  color: var(--ppqa-purple-bright) !important;
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
  background: linear-gradient(180deg, #ffffff 0%, #f7f2f9 100%) !important;
  border-radius: 12px;
  margin-top: 0.2rem;
}

/* ═══════════════════════════════════════════════════════════════════════
   Form inputs
   ═══════════════════════════════════════════════════════════════════════ */
.stApp .stTextInput input,
.stApp .stTextArea textarea {
  background: var(--ppqa-soft) !important;
  border: 1px solid var(--ppqa-border-strong) !important;
  border-radius: 10px;
  color: var(--ppqa-ink) !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   Metrics, DataFrames, Expanders
   ═══════════════════════════════════════════════════════════════════════ */
[data-testid="stMetric"] {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 14px;
  box-shadow: var(--ppqa-shadow-sm);
  padding: 0.75rem 0.85rem;
}

[data-testid="stMetricLabel"] p {
  color: var(--ppqa-muted) !important;
}

[data-testid="stMetricValue"] div {
  color: var(--ppqa-cyan) !important;
}

[data-testid="stDataFrame"] {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 14px;
  overflow: hidden;
}

div[data-testid="stExpander"] {
  background: rgba(255, 255, 255, 0.88) !important;
  border-color: var(--ppqa-border) !important;
  border-radius: 14px;
}

div[data-testid="stExpander"] p,
div[data-testid="stExpander"] span {
  color: var(--ppqa-ink) !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   Responsive
   ═══════════════════════════════════════════════════════════════════════ */
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

/* ═══════════════════════════════════════════════════════════════════════
   Nuclear dark-mode kill-switch
   Streamlit sometimes injects [data-theme="dark"] regardless of
   config.toml. Override every critical surface so no dark BG leaks.
   ═══════════════════════════════════════════════════════════════════════ */
html[data-theme="dark"],
[data-theme="dark"] .stApp,
.stApp[data-theme="dark"],
[data-theme="dark"] {
  --background-color: #faf8fb !important;
  --secondary-background-color: #f2edf6 !important;
  --text-color: #251a2d !important;
  --primary-color: #4f008c !important;
  color-scheme: light !important;
}

[data-theme="dark"] [data-testid="stChatInput"],
[data-theme="dark"] [data-testid="stChatInput"] > div,
[data-theme="dark"] [data-testid="stChatInput"] > div > div,
[data-theme="dark"] [data-testid="stChatMessage"],
[data-theme="dark"] [data-testid="stSidebar"],
[data-theme="dark"] [data-testid="stSidebar"] > div,
[data-theme="dark"] .stButton > button {
  background: var(--ppqa-surface) !important;
}

[data-theme="dark"] [data-testid="stBottom"] > div {
  background: linear-gradient(180deg, transparent, rgba(243, 238, 246, 0.97) 34%) !important;
}

/* Make sure avatar backgrounds survive dark mode */
[data-theme="dark"] [data-testid="stChatMessageAvatarUser"] {
  background: linear-gradient(135deg, var(--ppqa-stc-purple), var(--ppqa-purple-bright)) !important;
}

[data-theme="dark"] [data-testid="stChatMessageAvatarAssistant"] {
  background: linear-gradient(135deg, #d4f0f0, #e5f7f7) !important;
}

[data-theme="dark"] [data-testid="stChatMessageAvatarUser"] *,
[data-theme="dark"] [data-testid="stChatMessageAvatarUser"] svg {
  color: #ffffff !important;
  fill: #ffffff !important;
}

[data-theme="dark"] [data-testid="stChatMessageAvatarAssistant"] *,
[data-theme="dark"] [data-testid="stChatMessageAvatarAssistant"] svg {
  color: #007b80 !important;
  fill: #007b80 !important;
}
</style>
"""
