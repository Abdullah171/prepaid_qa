# Streamlit Frontend

Run the FastAPI backend first:

```bash
python -m uvicorn main:app --reload
```

Then start the Streamlit app:

```bash
python -m streamlit run frontend/app.py
```

The app reads `PPQA_API_BASE_URL` when set. Otherwise it calls `http://127.0.0.1:8000`.
The API URL is deployment-controlled by default. Trusted local environments can set
`PPQA_ALLOW_API_URL_EDIT=true` to expose the sidebar override.

Long analyses run in one bounded background worker per browser session. Streamlit
polls only the active status fragment, so the saved conversation does not fade or
rebuild on each progress update. API connections are pooled, metadata is cached
per browser session, and ordinary API calls use short timeouts. Use **Refresh** to
resync chat history changed by another browser.

Conditional charts are rendered from the versioned `chart` payload stored with
each assistant message. They appear both immediately and after reopening a chat,
independently of the **See source** toggle.

Requested CSV exports are rendered from the exact displayed Markdown table stored
with the assistant message, rather than from every internal result row. The buttons
are independent of **See source** and remain available when the conversation is
reopened.

Charts use an STC-themed palette. Line charts use a focused non-zero value scale
and monthly date results use month-level ticks, making small changes visible
without filling the x-axis with daily labels.
