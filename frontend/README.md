# Streamlit Frontend

Run the FastAPI backend first:

```bash
uv run uvicorn main:app --reload
```

Then start the Streamlit app:

```bash
uv run streamlit run frontend/app.py
```

The app reads `PPQA_API_BASE_URL` when set. Otherwise it calls `http://127.0.0.1:8000`.

The native chat composer includes microphone and Send controls together. A
submitted recording goes to the backend `/transcribe` route, and the returned
text is placed back into the composer for editing. Selecting Send again submits
the reviewed text for analysis. Browser microphone permission requires HTTPS
when the app is not running on localhost.

Conditional charts are rendered from the versioned `chart` payload stored with
each assistant message. They appear both immediately and after reopening a chat,
independently of the **See source** toggle.

Charts use an STC-themed palette. Line charts use a focused non-zero value scale
and monthly date results use month-level ticks, making small changes visible
without filling the x-axis with daily labels.
