"""Small, deployment-safe stylesheet for the Prepaid QA interface."""

APP_CSS = """
<style>
:root {
  --ppqa-purple: #4f008c;
  --ppqa-purple-hover: #3f0070;
  --ppqa-text: #251a2d;
  --ppqa-muted: #6f6475;
  --ppqa-border: #ded2e6;
  --ppqa-background: #faf7fc;
  --ppqa-surface: #ffffff;
  --ppqa-subtle: #f3edf7;
  --ppqa-success: #087b5b;
  --ppqa-danger: #b4233d;
}

/* Keep the app predictable even when the host or browser prefers dark mode. */
html,
html[data-theme="dark"],
.stApp,
[data-theme="dark"] .stApp {
  color-scheme: light !important;
  --background-color: var(--ppqa-background) !important;
  --secondary-background-color: var(--ppqa-subtle) !important;
  --text-color: var(--ppqa-text) !important;
  --primary-color: var(--ppqa-purple) !important;
}

.stApp {
  background: var(--ppqa-background) !important;
  color: var(--ppqa-text) !important;
}

.stApp,
.stApp button,
.stApp input,
.stApp textarea {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

header[data-testid="stHeader"] {
  background: var(--ppqa-background) !important;
  border-bottom: 1px solid #eee7f2;
}

.block-container {
  max-width: 960px;
  padding-bottom: 6rem;
  padding-top: 1rem;
}

.stMain [data-testid="stElementContainer"][data-stale="true"] {
  opacity: 1 !important;
  transition: none !important;
}

/* Sidebar */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {
  background: #f1eaf5 !important;
}

[data-testid="stSidebar"] {
  border-right: 1px solid var(--ppqa-border) !important;
}

[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.65rem; }

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span:not([data-testid="stIconMaterial"]) {
  color: var(--ppqa-text) !important;
}

[data-testid="stSidebar"] hr {
  border-color: var(--ppqa-border);
  margin: 0.25rem 0;
}

.ppqa-brand {
  align-items: center;
  background: var(--ppqa-surface);
  border: 1px solid var(--ppqa-border);
  border-radius: 10px;
  display: flex;
  gap: 0.75rem;
  margin: 0 0 0.55rem;
  padding: 0.8rem;
}

.ppqa-brand-mark {
  align-items: center;
  background: var(--ppqa-purple);
  border-radius: 8px;
  color: #ffffff !important;
  display: flex;
  flex: 0 0 auto;
  font-size: 0.82rem;
  font-weight: 750;
  height: 38px;
  justify-content: center;
  width: 38px;
}

.ppqa-brand-title {
  color: var(--ppqa-text) !important;
  font-size: 0.98rem;
  font-weight: 700;
  line-height: 1.25;
}

.ppqa-brand-subtitle {
  color: var(--ppqa-muted) !important;
  font-size: 0.74rem;
  margin-top: 0.12rem;
}

.ppqa-section-label {
  color: var(--ppqa-muted) !important;
  font-size: 0.71rem;
  font-weight: 700;
  letter-spacing: 0.045em;
  padding-top: 0.3rem;
  text-transform: uppercase;
}

.ppqa-session-meta {
  color: var(--ppqa-muted) !important;
  font-size: 0.7rem;
  margin: -0.4rem 0 0.1rem;
  padding-left: 0.4rem;
}

.ppqa-health {
  align-items: center;
  background: #fff5f5;
  border: 1px solid #f2c8cf;
  border-radius: 8px;
  color: var(--ppqa-danger) !important;
  display: inline-flex;
  font-size: 0.76rem;
  font-weight: 650;
  gap: 0.4rem;
  padding: 0.35rem 0.55rem;
}

.ppqa-health span {
  background: var(--ppqa-danger) !important;
  border-radius: 50%;
  display: inline-block;
  height: 0.42rem;
  width: 0.42rem;
}

/* Streamlit exposes st.toggle as stCheckbox in the browser. Style both the
   hidden checkbox state and the separate visual track so host themes cannot
   turn the off state white-on-white. */
[data-testid="stSidebar"] [data-testid="stCheckbox"] label,
[data-testid="stSidebar"] [data-testid="stCheckbox"] p {
  color: var(--ppqa-text) !important;
  font-size: 0.88rem;
  opacity: 1 !important;
}

[data-testid="stSidebar"] [data-testid="stCheckbox"] input[type="checkbox"] ~ div:first-of-type,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label > div:first-of-type {
  background-color: #b6a6c1 !important;
  border: 1px solid #a593b2 !important;
  box-sizing: border-box !important;
  opacity: 1 !important;
}

[data-testid="stSidebar"] [data-testid="stCheckbox"] input[type="checkbox"] ~ div:first-of-type > div,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label > div:first-of-type > div {
  background-color: #ffffff !important;
  box-shadow: 0 1px 2px rgba(37, 26, 45, 0.28) !important;
}

[data-testid="stSidebar"] [data-testid="stCheckbox"] input[type="checkbox"]:checked ~ div:first-of-type,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label[data-selected] > div:first-of-type,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input[type="checkbox"]:checked) > div:first-of-type {
  background-color: var(--ppqa-purple) !important;
  border-color: var(--ppqa-purple) !important;
}

[data-testid="stSidebar"] [data-testid="stCheckbox"] label[data-disabled] > div:first-of-type {
  opacity: 0.55 !important;
}

[data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg {
  color: var(--ppqa-muted) !important;
}

/* Page header */
.ppqa-header {
  align-items: center;
  border-bottom: 1px solid var(--ppqa-border);
  display: flex;
  justify-content: space-between;
  margin-bottom: 1.25rem;
  min-height: 72px;
  padding: 0 0 0.9rem;
}

.ppqa-eyebrow {
  color: var(--ppqa-muted) !important;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  margin-bottom: 0.2rem;
  text-transform: uppercase;
}

.ppqa-title {
  color: var(--ppqa-text) !important;
  font-size: 1.3rem;
  font-weight: 720;
  line-height: 1.25;
}

.ppqa-subtitle {
  color: var(--ppqa-muted) !important;
  font-size: 0.82rem;
  margin-top: 0.16rem;
}

.ppqa-header-status {
  align-items: center;
  background: #f2f8f5;
  border: 1px solid #cfe5da;
  border-radius: 8px;
  color: var(--ppqa-success) !important;
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 0.74rem;
  font-weight: 650;
  gap: 0.4rem;
  padding: 0.35rem 0.55rem;
}

.ppqa-header-status span {
  background: var(--ppqa-success) !important;
  border-radius: 50%;
  display: inline-block;
  height: 0.42rem;
  width: 0.42rem;
}

/* Empty state */
.ppqa-empty {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border);
  border-radius: 12px;
  padding: 1.4rem;
}

.ppqa-empty-lead {
  align-items: center;
  display: flex;
  gap: 0.85rem;
}

.ppqa-empty-icon {
  align-items: center;
  background: #f1eaf6;
  border-radius: 9px;
  display: flex;
  flex: 0 0 auto;
  height: 44px;
  justify-content: center;
  position: relative;
  width: 44px;
}

.ppqa-empty-icon::before,
.ppqa-empty-icon::after {
  background: var(--ppqa-purple);
  border-radius: 4px;
  content: "";
  position: absolute;
}

.ppqa-empty-icon::before { height: 18px; width: 4px; }
.ppqa-empty-icon::after { height: 4px; width: 18px; }
.ppqa-empty-icon span { display: none; }

.ppqa-empty-kicker {
  color: var(--ppqa-purple) !important;
  font-size: 0.71rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  margin-bottom: 0.15rem;
  text-transform: uppercase;
}

.ppqa-empty-title {
  color: var(--ppqa-text) !important;
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1.3;
}

.ppqa-empty-copy {
  color: var(--ppqa-muted) !important;
  font-size: 0.86rem;
  line-height: 1.5;
  margin-top: 0.15rem;
}

.ppqa-topics {
  display: grid;
  gap: 0.65rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 1rem;
}

.ppqa-topic {
  align-items: center;
  background: var(--ppqa-subtle) !important;
  border: 1px solid #e5e7eb;
  border-radius: 9px;
  display: flex;
  gap: 0.6rem;
  min-width: 0;
  padding: 0.7rem;
}

.ppqa-topic-dot {
  background: var(--ppqa-purple) !important;
  border-radius: 50%;
  flex: 0 0 auto;
  height: 0.45rem;
  width: 0.45rem;
}

.ppqa-topic-cyan { background: #008c95 !important; }
.ppqa-topic-magenta { background: #d92d55 !important; }

.ppqa-topic strong,
.ppqa-topic small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ppqa-topic strong { color: var(--ppqa-text) !important; font-size: 0.79rem; }
.ppqa-topic small { color: var(--ppqa-muted) !important; font-size: 0.69rem; margin-top: 0.1rem; }

.ppqa-empty-hint {
  border-top: 1px solid var(--ppqa-border);
  color: var(--ppqa-muted) !important;
  font-size: 0.8rem;
  line-height: 1.45;
  margin-top: 1rem;
  padding-top: 0.8rem;
}

.ppqa-empty-hint span {
  color: var(--ppqa-purple) !important;
  font-size: 0.7rem;
  font-weight: 700;
  margin-right: 0.35rem;
  text-transform: uppercase;
}

/* Chat */
div[data-testid="stChatMessage"] {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 10px;
  margin-bottom: 0.7rem;
  padding: 0.6rem 0.75rem;
}

div[data-testid="stChatMessage"] p,
div[data-testid="stChatMessage"] li { color: var(--ppqa-text) !important; }

/* Markdown content has its own table and code defaults. Pin every layer to the
   app palette so a dark host theme cannot leave white text on a transparent
   table (or a dark SQL block inside an otherwise light message). */
.stApp [data-testid="stMarkdownContainer"] {
  color: var(--ppqa-text) !important;
}

.stApp [data-testid="stMarkdownContainer"] h1,
.stApp [data-testid="stMarkdownContainer"] h2,
.stApp [data-testid="stMarkdownContainer"] h3,
.stApp [data-testid="stMarkdownContainer"] h4,
.stApp [data-testid="stMarkdownContainer"] h5,
.stApp [data-testid="stMarkdownContainer"] h6,
.stApp [data-testid="stMarkdownContainer"] strong {
  color: var(--ppqa-text) !important;
}

.stApp [data-testid="stMarkdownContainer"] a {
  color: var(--ppqa-purple) !important;
}

.stApp [data-testid="stMarkdownContainer"] blockquote {
  background: var(--ppqa-subtle) !important;
  border-left-color: var(--ppqa-purple) !important;
  color: var(--ppqa-text) !important;
}

.stApp [data-testid="stMarkdownContainer"] table {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-collapse: separate !important;
  border-radius: 8px;
  border-spacing: 0 !important;
  color: var(--ppqa-text) !important;
  display: block;
  margin: 0.75rem 0 1rem;
  max-width: 100%;
  overflow-x: auto;
  width: max-content;
}

.stApp [data-testid="stMarkdownContainer"] thead,
.stApp [data-testid="stMarkdownContainer"] thead tr,
.stApp [data-testid="stMarkdownContainer"] th {
  background: var(--ppqa-subtle) !important;
  color: var(--ppqa-text) !important;
}

.stApp [data-testid="stMarkdownContainer"] tbody,
.stApp [data-testid="stMarkdownContainer"] tbody tr,
.stApp [data-testid="stMarkdownContainer"] td {
  background: var(--ppqa-surface) !important;
  color: var(--ppqa-text) !important;
}

.stApp [data-testid="stMarkdownContainer"] tbody tr:nth-child(even),
.stApp [data-testid="stMarkdownContainer"] tbody tr:nth-child(even) td {
  background: #fcfafc !important;
}

.stApp [data-testid="stMarkdownContainer"] th,
.stApp [data-testid="stMarkdownContainer"] td {
  border-bottom: 1px solid var(--ppqa-border) !important;
  border-right: 1px solid var(--ppqa-border) !important;
  min-width: 7rem;
  padding: 0.55rem 0.7rem !important;
  text-align: left;
  vertical-align: top;
  white-space: normal;
}

.stApp [data-testid="stMarkdownContainer"] th:last-child,
.stApp [data-testid="stMarkdownContainer"] td:last-child {
  border-right: 0 !important;
}

.stApp [data-testid="stMarkdownContainer"] tbody tr:last-child td {
  border-bottom: 0 !important;
}

.stApp [data-testid="stMarkdownContainer"] code:not([data-testid="stCode"] code):not([data-testid="stCodeBlock"] code) {
  background: var(--ppqa-subtle) !important;
  border: 1px solid var(--ppqa-border);
  border-radius: 4px;
  color: var(--ppqa-purple-hover) !important;
  padding: 0.08em 0.3em;
}

div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: #f6f0f9 !important;
}

[data-testid="stChatMessageAvatarUser"] {
  background: var(--ppqa-purple) !important;
  border-radius: 8px !important;
}

[data-testid="stChatMessageAvatarUser"] * { color: #ffffff !important; }

[data-testid="stChatMessageAvatarAssistant"] {
  background: #e8f4f4 !important;
  border-radius: 8px !important;
}

[data-testid="stChatMessageAvatarAssistant"] * { color: #08777d !important; }

div[data-testid="stChatInput"],
div[data-testid="stChatInput"] > div { background: var(--ppqa-surface) !important; }

div[data-testid="stChatInput"] {
  border: 1px solid #bbaac6 !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 14px rgba(16, 24, 40, 0.08);
  overflow: hidden;
}

div[data-testid="stChatInput"]:focus-within {
  border-color: var(--ppqa-purple) !important;
  box-shadow: 0 0 0 2px rgba(79, 0, 140, 0.12);
}

div[data-testid="stChatInput"] textarea {
  background: var(--ppqa-surface) !important;
  color: var(--ppqa-text) !important;
  caret-color: var(--ppqa-purple) !important;
}

div[data-testid="stChatInput"] textarea::placeholder { color: #7b818b !important; }

div[data-testid="stChatInput"] button {
  background: var(--ppqa-purple) !important;
  border-radius: 8px !important;
  color: #ffffff !important;
}

div[data-testid="stChatInput"] button * { color: #ffffff !important; }

div[data-testid="stChatInput"] button svg {
  height: 1.25rem !important;
  width: 1.25rem !important;
}

[data-testid="stBottom"] > div {
  background: linear-gradient(180deg, transparent, #faf7fc 32%) !important;
  padding-top: 1.25rem;
}

/* Explicit rules prevent a host dark theme from making chat rows black. */
.stApp .stButton button,
.stApp .stDownloadButton button,
.stApp [data-testid="stSidebar"] .stButton button,
[data-theme="dark"] .stApp .stButton button {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 8px;
  color: var(--ppqa-text) !important;
  font-weight: 600;
}

.stApp .stButton button p,
.stApp .stButton button span,
.stApp .stDownloadButton button p,
.stApp .stDownloadButton button span { color: inherit !important; }

/* Streamlit SVGs use transparent paths for their view-box background. Keep
   those paths transparent or icons such as send and copy become solid boxes. */
.stApp button svg[fill="none"],
.stApp button svg [fill="none"] {
  fill: none !important;
}

.stApp .stButton button:hover,
.stApp .stDownloadButton button:hover {
  background: #f3edf7 !important;
  border-color: #bca9c8 !important;
  color: var(--ppqa-text) !important;
}

.stApp .stButton button[kind="primary"],
.stApp .stButton button[data-testid="stBaseButton-primary"] {
  background: var(--ppqa-purple) !important;
  border-color: var(--ppqa-purple) !important;
  color: #ffffff !important;
}

.stApp .stButton button[kind="primary"]:hover,
.stApp .stButton button[data-testid="stBaseButton-primary"]:hover {
  background: var(--ppqa-purple-hover) !important;
  border-color: var(--ppqa-purple-hover) !important;
  color: #ffffff !important;
}

.stApp .stButton button[kind="tertiary"],
.stApp .stButton button[data-testid="stBaseButton-tertiary"] {
  background: transparent !important;
  border-color: transparent !important;
  color: var(--ppqa-purple) !important;
}

.stApp .stButton button:focus-visible,
.stApp .stTextInput input:focus-visible,
.stApp .stTextArea textarea:focus-visible {
  outline: 2px solid rgba(79, 0, 140, 0.25) !important;
  outline-offset: 2px;
}

[data-testid="stSidebar"] .stButton button { min-height: 2.3rem; }
[data-testid="stSidebar"] [data-testid="stIconMaterial"] { color: inherit !important; }

/* Hosted Streamlit may insert a tooltip wrapper between stButton and the
   actual button. Target the stable button test ID directly. */
[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
  background: #ffffff !important;
  background-image: none !important;
  border-color: var(--ppqa-border) !important;
  color: var(--ppqa-text) !important;
}

[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] * {
  color: var(--ppqa-text) !important;
}

/* The main sidebar action should be prominent without becoming a large solid
   purple slab. Its explicit key keeps this from changing history buttons. */
[data-testid="stSidebar"] .st-key-new-analysis button {
  background: var(--ppqa-surface) !important;
  border-color: var(--ppqa-purple) !important;
  color: var(--ppqa-purple) !important;
}

[data-testid="stSidebar"] .st-key-new-analysis button:hover {
  background: var(--ppqa-subtle) !important;
  border-color: var(--ppqa-purple-hover) !important;
  color: var(--ppqa-purple-hover) !important;
}

[data-testid="stSidebar"] .st-key-new-analysis button [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] .st-key-new-analysis button p,
[data-testid="stSidebar"] .st-key-new-analysis button span {
  color: inherit !important;
}

/* Active analysis stop control */
.st-key-active-composer { position: relative; }
.st-key-active-composer [data-testid="stChatInput"] button { visibility: hidden; }
.st-key-active-composer .st-key-stop-analysis {
  bottom: 0.52rem;
  position: absolute;
  right: 0.65rem;
  width: 8rem;
  z-index: 10;
}
.st-key-active-composer .stButton { width: 8rem; }
.st-key-active-composer .stButton button {
  align-items: center;
  background: #fff5f6 !important;
  border: 1px solid #d92d55 !important;
  border-radius: 8px;
  color: #a7193f !important;
  display: flex;
  height: 2.15rem;
  justify-content: center;
  min-height: 2.15rem;
  padding: 0 0.7rem;
  width: 8rem;
}

.st-key-active-composer .stButton button:hover {
  background: #fde8ed !important;
  border-color: #b4233d !important;
  color: #8f1735 !important;
}

.st-key-active-composer .stButton button *,
.st-key-active-composer .stButton [data-testid="stIconMaterial"] {
  color: inherit !important;
  white-space: nowrap;
}

.st-key-active-composer .stButton button:disabled {
  opacity: 0.6 !important;
}

/* Progress, inputs, and data components */
@keyframes ppqa-spin { to { transform: rotate(360deg); } }

.ppqa-non-thinking-progress {
  align-items: center;
  color: var(--ppqa-muted) !important;
  display: inline-flex;
  font-size: 0.86rem;
  gap: 0.6rem;
  min-height: 2.25rem;
}

.ppqa-progress-spinner {
  animation: ppqa-spin 700ms linear infinite;
  border: 2px solid #ded5e5 !important;
  border-radius: 50%;
  border-top-color: var(--ppqa-purple) !important;
  height: 1.1rem;
  width: 1.1rem;
}

.st-key-live-thinking [data-testid="stIconMaterial"] { animation: ppqa-spin 700ms linear infinite !important; }
.st-key-live-thinking-content { background: var(--ppqa-subtle) !important; border-radius: 8px; }

.stApp .stTextInput input,
.stApp .stTextArea textarea {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  color: var(--ppqa-text) !important;
}

[data-testid="stMetric"],
[data-testid="stDataFrame"],
div[data-testid="stExpander"] {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 8px;
}

[data-testid="stMetric"] { padding: 0.7rem 0.8rem; }
[data-testid="stMetricLabel"] p { color: var(--ppqa-muted) !important; }
[data-testid="stMetricValue"] div { color: var(--ppqa-text) !important; }
div[data-testid="stExpander"] details,
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
  background: var(--ppqa-surface) !important;
  color: var(--ppqa-text) !important;
}

div[data-testid="stExpander"] summary:hover {
  background: var(--ppqa-subtle) !important;
}

div[data-testid="stExpander"] p,
div[data-testid="stExpander"] span,
div[data-testid="stExpander"] svg {
  color: var(--ppqa-text) !important;
}

/* st.code is rendered by a syntax highlighter outside the regular Markdown
   element. Override both its wrapper and nested inline styles. */
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]),
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) > div,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) pre,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) code {
  background: #f7f3f9 !important;
  background-color: #f7f3f9 !important;
  color: var(--ppqa-text) !important;
  text-shadow: none !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) {
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 8px !important;
  overflow: hidden;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) pre {
  border: 0 !important;
  margin: 0 !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) button {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  color: var(--ppqa-text) !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) button:hover {
  background: var(--ppqa-subtle) !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) button *,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) button svg {
  color: inherit !important;
}

/* Query-result previews use regular HTML instead of Streamlit's canvas grid.
   Canvas colors follow the host theme and cannot be corrected reliably with
   CSS; this table remains readable on every deployment host. */
.ppqa-result-table-wrap {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border);
  border-radius: 8px;
  max-height: 24rem;
  overflow: auto;
  width: 100%;
}

.stApp [data-testid="stMarkdownContainer"] .ppqa-result-table {
  border: 0 !important;
  border-radius: 0;
  display: table;
  margin: 0;
  min-width: 100%;
  overflow: visible;
  width: max-content;
}

.stApp [data-testid="stMarkdownContainer"] .ppqa-result-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.comment,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.prolog,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.doctype,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.cdata {
  color: var(--ppqa-muted) !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.keyword,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.boolean,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.constant {
  color: var(--ppqa-purple) !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.string,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.char,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.attr-value {
  color: var(--ppqa-success) !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.number,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.function,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.builtin {
  color: #9a3f00 !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.operator,
.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) .token.punctuation {
  color: #514858 !important;
}

@media (max-width: 720px) {
  .block-container { padding-top: 0.65rem; }
  .ppqa-header { min-height: 64px; }
  .ppqa-header-status { display: none; }
  .ppqa-topics { grid-template-columns: 1fr; }
  .ppqa-empty { padding: 1rem; }
  .ppqa-empty-lead { align-items: flex-start; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0.01ms !important; }
  .ppqa-progress-spinner,
  .st-key-live-thinking [data-testid="stIconMaterial"] { animation-duration: 1.4s !important; }
}
</style>
"""
