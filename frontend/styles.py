"""Small, deployment-safe stylesheet for the Prepaid QA interface."""

APP_CSS = """
<style>
:root {
  --ppqa-purple: #4f008c;
  --ppqa-purple-hover: #3f0070;
  --ppqa-text: #1d2939;
  --ppqa-muted: #667085;
  --ppqa-border: #e4e7ec;
  --ppqa-background: #ffffff;
  --ppqa-surface: #ffffff;
  --ppqa-subtle: #f6f7f9;
  --ppqa-success: #087b5b;
  --ppqa-danger: #b4233d;
  --ppqa-shadow-sm: 0 1px 2px rgba(16, 24, 40, 0.04);
  --ppqa-shadow-md: 0 8px 28px rgba(16, 24, 40, 0.05);
  --ppqa-transition: 180ms cubic-bezier(0.2, 0, 0, 1);
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

.stMain,
[data-testid="stMain"] { background: #f7f8fb !important; }

html { scroll-behavior: smooth; }

* {
  scrollbar-color: #cfd4dc transparent;
  scrollbar-width: thin;
}

*::-webkit-scrollbar { height: 8px; width: 8px; }
*::-webkit-scrollbar-track { background: transparent; }
*::-webkit-scrollbar-thumb {
  background: #cfd4dc;
  border: 2px solid transparent;
  border-radius: 999px;
  background-clip: padding-box;
}

*::-webkit-scrollbar-thumb:hover { background-color: #98a2b3; }

.stApp,
.stApp button,
.stApp input,
.stApp textarea {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

header[data-testid="stHeader"] {
  background: #ffffff !important;
  border-bottom: 0;
}

.block-container {
  max-width: 1320px;
  padding-bottom: 7rem;
  padding-top: 1.25rem;
}

.stMain [data-testid="stElementContainer"][data-stale="true"] {
  opacity: 1 !important;
  transition: none !important;
}

/* Sidebar */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {
  background: #ffffff !important;
}

[data-testid="stSidebar"] {
  border-right: 1px solid var(--ppqa-border) !important;
  min-width: 20rem !important;
  width: 20rem !important;
}

[data-testid="stSidebar"] > div:first-child { padding: 1.5rem 1.35rem 1rem; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.85rem; }

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
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  display: flex;
  gap: 0.9rem;
  margin: 0.75rem 0 0.8rem;
  padding: 0;
}

.ppqa-brand-mark {
  align-items: center;
  background: var(--ppqa-purple);
  border-radius: 9px;
  color: #ffffff !important;
  display: flex;
  flex: 0 0 auto;
  font-size: 0.95rem;
  font-weight: 750;
  height: 50px;
  justify-content: center;
  width: 50px;
}

.ppqa-brand-title {
  color: var(--ppqa-text) !important;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.25;
}

.ppqa-brand-subtitle {
  color: var(--ppqa-muted) !important;
  font-size: 0.75rem;
  margin-top: 0.12rem;
}

.ppqa-section-label {
  color: var(--ppqa-muted) !important;
  font-size: 0.82rem;
  font-weight: 500;
  letter-spacing: 0;
  padding-top: 0.3rem;
  text-transform: none;
}

.ppqa-session-meta {
  color: var(--ppqa-muted) !important;
  font-size: 0.7rem;
  margin: -0.4rem 0 0.1rem;
  padding-left: 0.4rem;
}

.ppqa-health {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 0;
  color: var(--ppqa-danger) !important;
  display: inline-flex;
  font-size: 0.76rem;
  font-weight: 650;
  gap: 0.4rem;
  padding: 0.25rem 0;
}

.ppqa-health span {
  background: var(--ppqa-danger) !important;
  border-radius: 50%;
  display: inline-block;
  height: 0.42rem;
  width: 0.42rem;
}

.ppqa-health-ok { color: var(--ppqa-success) !important; }
.ppqa-health-ok span { background: var(--ppqa-success) !important; }
.ppqa-health-bad { color: var(--ppqa-danger) !important; }
.ppqa-health-bad span { background: var(--ppqa-danger) !important; }

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
  background-color: #d0d5dd !important;
  border: 1px solid #c5cad3 !important;
  box-sizing: border-box !important;
  opacity: 1 !important;
  transition: background-color 0.2s ease, border-color 0.2s ease !important;
}

[data-testid="stSidebar"] [data-testid="stCheckbox"] input[type="checkbox"] ~ div:first-of-type > div,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label > div:first-of-type > div {
  background-color: var(--ppqa-surface) !important;
  box-shadow: 0 1px 2px rgba(37, 26, 45, 0.28) !important;
  transition: transform 0.2s ease !important;
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
  border-bottom: 0;
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  min-height: 32px;
  padding: 0;
}

.ppqa-title {
  color: var(--ppqa-muted) !important;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.25;
}

.ppqa-header-rule {
  background: #dfe3ea;
  height: 1px;
  margin-bottom: 1.25rem;
  position: relative;
  width: 100%;
}

.ppqa-header-rule span {
  background: linear-gradient(90deg, var(--ppqa-purple) 0 38%, #00aeb3 60%, #e9345a 100%);
  display: block;
  height: 3px;
  left: 0;
  position: absolute;
  top: -1px;
  width: 9rem;
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
  box-shadow: var(--ppqa-shadow-md);
  display: flex;
  min-height: 420px;
  padding: 3rem;
}

.ppqa-empty-lead {
  align-items: center;
  display: flex;
  gap: 1.5rem;
  margin-left: 0.5rem;
}

.ppqa-empty-accent {
  align-self: stretch;
  background: var(--ppqa-purple);
  border-radius: 2px;
  flex: 0 0 4px;
  min-height: 112px;
}

.ppqa-empty-kicker {
  color: var(--ppqa-purple) !important;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  margin-bottom: 1rem;
  text-transform: uppercase;
}

.ppqa-empty-title {
  color: var(--ppqa-text) !important;
  font-size: 1.65rem;
  font-weight: 750;
  line-height: 1.3;
}

.ppqa-empty-copy {
  color: var(--ppqa-muted) !important;
  font-size: 1rem;
  line-height: 1.5;
  margin-top: 0.9rem;
}

/* Chat */
div[data-testid="stChatMessage"] {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 14px;
  box-shadow: var(--ppqa-shadow-sm);
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
  background: #fafbfc !important;
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
  background: #f8f9fb !important;
}

[data-testid="stChatMessageAvatarUser"] {
  background: var(--ppqa-purple) !important;
  border-radius: 8px !important;
}

[data-testid="stChatMessageAvatarUser"] * { color: #ffffff !important; }

[data-testid="stChatMessageAvatarAssistant"] {
  background: #ffffff !important;
  border-radius: 8px !important;
  border: 1px solid var(--ppqa-border) !important;
}

[data-testid="stChatMessageAvatarAssistant"] * { color: var(--ppqa-purple) !important; }

div[data-testid="stChatInput"],
div[data-testid="stChatInput"] > div { background: #f0f2f6 !important; }

div[data-testid="stChatInput"] {
  background: #f0f2f6 !important;
  border: 1px solid transparent !important;
  border-radius: 12px !important;
  box-shadow: none;
  overflow: hidden;
  transition: border-color var(--ppqa-transition), box-shadow var(--ppqa-transition);
}

div[data-testid="stChatInput"]:focus-within {
  border-color: var(--ppqa-purple) !important;
  box-shadow: 0 0 0 3px rgba(79, 0, 140, 0.08);
}

div[data-testid="stChatInput"] textarea {
  background: #f0f2f6 !important;
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

div[data-testid="stChatInput"] button:disabled {
  background: #e1e5ed !important;
  color: #98a2b3 !important;
  opacity: 1 !important;
}

div[data-testid="stChatInput"] button:disabled * { color: #98a2b3 !important; }

div[data-testid="stChatInput"] button svg {
  height: 1.25rem !important;
  width: 1.25rem !important;
}

[data-testid="stBottom"] > div {
  background: #ffffff !important;
  border-top: 1px solid #f2f4f7;
  padding-bottom: 1rem;
  padding-top: 1rem;
}

/* Explicit rules prevent a host dark theme from making chat rows black. */
.stApp .stButton button,
.stApp .stDownloadButton button,
.stApp [data-testid="stSidebar"] .stButton button,
[data-theme="dark"] .stApp .stButton button {
  background: var(--ppqa-surface) !important;
  border: 1px solid var(--ppqa-border) !important;
  border-radius: 10px;
  box-shadow: var(--ppqa-shadow-sm);
  color: var(--ppqa-text) !important;
  font-weight: 600;
  transition: background-color var(--ppqa-transition), border-color var(--ppqa-transition), color var(--ppqa-transition), box-shadow var(--ppqa-transition), transform var(--ppqa-transition) !important;
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
  background: var(--ppqa-subtle) !important;
  border-color: #cfd4dc !important;
  box-shadow: 0 3px 8px rgba(16, 24, 40, 0.08);
  color: var(--ppqa-text) !important;
  transform: none;
}

.stApp .stButton button:active,
.stApp .stDownloadButton button:active {
  box-shadow: var(--ppqa-shadow-sm);
  transform: translateY(0);
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
  background: var(--ppqa-surface) !important;
  background-image: none !important;
  border-color: var(--ppqa-border) !important;
  color: var(--ppqa-text) !important;
}

[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] * {
  color: var(--ppqa-text) !important;
}

[data-testid="stSidebar"] .st-key-new-chat button {
  background: var(--ppqa-purple) !important;
  border-color: var(--ppqa-purple) !important;
  color: #ffffff !important;
  min-height: 2.75rem;
}

[data-testid="stSidebar"] .st-key-new-chat button:hover {
  background: var(--ppqa-purple-hover) !important;
  border-color: var(--ppqa-purple-hover) !important;
  color: #ffffff !important;
}

[data-testid="stSidebar"] .st-key-new-chat button p,
[data-testid="stSidebar"] .st-key-new-chat button span {
  color: #ffffff !important;
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
  border-radius: 12px;
  box-shadow: var(--ppqa-shadow-sm);
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
  background: #f7f8fa !important;
  background-color: #f7f8fa !important;
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
  overflow-x: hidden !important;
  white-space: pre-wrap !important;
}

.stApp :is([data-testid="stCode"], [data-testid="stCodeBlock"]) pre code {
  overflow-wrap: anywhere;
  white-space: inherit !important;
  word-break: break-word;
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
  border-radius: 12px;
  box-shadow: var(--ppqa-shadow-sm);
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
  .ppqa-empty { min-height: 280px; padding: 1.5rem; }
  .ppqa-empty-lead { align-items: flex-start; }
  .ppqa-empty-title { font-size: 1.35rem; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 0.01ms !important; }
  html { scroll-behavior: auto; }
  .ppqa-progress-spinner,
  .st-key-live-thinking [data-testid="stIconMaterial"] { animation-duration: 1.4s !important; }
}
</style>
"""
