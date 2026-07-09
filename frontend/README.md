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
