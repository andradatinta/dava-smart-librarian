# Dava — Smart Librarian 📚

A tiny Retrieval-Augmented Generation (RAG) app that recommends **one perfect book** for a user’s vibe/theme request, returns a **concise reason + full summary**, supports **multi-language queries/answers**, and can **read the answer aloud** (Text-to-Speech).

- **Backend:** FastAPI · OpenAI Responses API · ChromaDB (embeddings/vector search)
- **Frontend:** React (Vite) · TailwindCSS · Framer Motion · React Markdown
- **Infra:** Docker (multi-stage) · Poetry (deps)
- **Data:** JSON book entries → embedded into Chroma (local persistent volume)

> ✅ The Docker setup serves the built React app directly from FastAPI, so you only expose a single port: `http://localhost:8000/`.

---

## ✨ Features

- **Book RAG**: semantic search over a local vector DB (ChromaDB) for book titles/summaries.
- **Language auto-detection**: answers in the **same language** as the prompt (e.g., English / Romanian).
- **Guardrails**:

  - Only answer **book-related** requests (classifies chit-chat/other and declines politely).
  - If the user asks for a **specific person/title** not in the collection, decline instead of “creative substitutions.”

- **Text-to-Speech (TTS)**: `/tts` endpoint returns an MP3 for the recommendation (front-end adds a **Listen** button).
- **Inappropriate language filter**: every user query is checked with OpenAI’s `omni-moderation-latest` model; flagged queries are politely declined instead of being sent to the LLM.
- **Modern front-end**: compact cards, centered answer panel, smooth animations, markdown rendering for bolding, etc.
- **No secrets in repo**: OpenAI key is provided via **environment variable** (Compose `.env` or host env).

---

## 🗂 Folder Structure

```
dava-smart-librarian/
├─ backend/
│  ├─ api.py                # FastAPI app (serves SPA at "/"; APIs at /chat, /tts, /health, /debug/search)
│  ├─ retriever.py          # Chroma client + search + helpers (get_summary_by_title, etc.)
│  ├─ scripts/
│  │  ├─ generate_books.py  # uses OpenAI to synthesize real-book entries (title/themes/summary) → JSON
│  │  └─ ingest_chroma.py   # reads JSON, makes embeddings, upserts into Chroma
│  ├─ pyproject.toml        # Poetry 2.x: package-mode=false (deps only)
│  └─ ...                   # other backend code
├─ frontend/
│  ├─ src/App.jsx, components/...  # React app (Vite)
│  └─ package.json
├─ Dockerfile               # multi-stage: Node build → Python runtime
├─ docker-compose.yml       # passes OPENAI_API_KEY at runtime; volume for .chroma
└─ README.md
```

---

## 🔑 Environment Variables

| Variable         | Where it’s used | Required | Notes                                                |
| ---------------- | --------------- | -------- | ---------------------------------------------------- |
| `OPENAI_API_KEY` | Backend         | ✅       | Your OpenAI API key (not committed).                 |
| `CHROMA_DIR`     | Backend         | ❌       | Defaults to `.chroma` (persisted volume via Docker). |

**How to set:**

- **PowerShell (Windows):**

  ```powershell
  $Env:OPENAI_API_KEY="sk-XXXX..."
  ```

- **CMD (Windows):**

  ```cmd
  set OPENAI_API_KEY=sk-XXXX...
  ```

- **macOS/Linux (bash):**

  ```bash
  export OPENAI_API_KEY=sk-XXXX...
  ```

You can also create a **root** `.env` (next to `docker-compose.yml`) containing:

```
OPENAI_API_KEY=sk-XXXX...
```

> This is a **Compose env file** (not `backend/.env`). It is not baked into the image; it injects at runtime.

---

## ▶️ Run with Docker (recommended)

1. **Set your key** in the shell (or use a root `.env` as above).
2. From the project root (where `Dockerfile` and `docker-compose.yml` live):

```bash
docker compose build --no-cache
docker compose up
```

- Open the app: **[http://localhost:8000](http://localhost:8000)**
- Backend endpoints:

  - `GET /health` – quick diagnostics (env/key presence preview, etc.)
  - `GET /debug/search?q=<query>&k=3` – see raw vector search hits (for debugging)
  - `POST /chat` – main RAG endpoint (JSON body: `{ "query": "...", "k": 3 }`)
  - `POST /tts` – text → MP3 (JSON body: `{ "text": "...", "voice": "alloy" }`)

> The Chroma database is persisted in a Docker **volume** named `chroma_data`.

---

## 🧠 How it Works (RAG Flow)

1. **Embedding & indexing (one-time or as needed)**

   - `scripts/generate_books.py` (optional): uses the **OpenAI Responses API** to synthesize **real** book entries (title, summary, themes) into JSON.
   - `scripts/ingest_chroma.py`: reads JSON, creates **embeddings** with `text-embedding-3-small`, upserts into **ChromaDB** with metadata:

     - `title` (string),
     - `summary` (string),
     - `themes` (comma-separated list like `"friendship, magic, courage"`),
     - `document` (the text embedded, typically `summary`).

2. **Query time**

   - Detect prompt language once (Responses API mini prompt); answer in that language.
   - **Guardrail A (intent):** If not a book request → polite decline (same language).
   - **Guardrail B (exact match):** If user asks about a **specific person/title** and it’s **not** in the collection → decline (no creative substitutes).
   - Embed query → **vector search** in Chroma → top-k hits.
   - Ask model to choose **exactly one title** from context (or empty if nothing is good).
   - Fetch the stored summary/metadata for the chosen title (**server-side “tool call”**).
   - Compose a **concise recommendation** in user’s language (reason + full summary).

3. **Optional TTS**

   - `/tts` uses OpenAI **audio.speech** (or equivalent) to generate **MP3** from the final answer; front-end plays it.

---

## 🧩 Tech Stack & Libraries

- **FastAPI** (backend web framework)
- **OpenAI Python SDK** (`openai>=1.101.0`):

  - **Responses API** (`client.responses.create(...)`) for language detection, selection, final composition
  - **Embeddings API** (`text-embedding-3-small`) for vector search
  - **Moderation** (`omni-moderation-latest`) – optional guardrail (inappropriate language filter)
  - **TTS** (speech synthesis to MP3)

- **ChromaDB** (`chromadb>=1.0.20`): persistent local vector store (.hnsw index), queried via cosine distance.
- **React + Vite** (frontend), **TailwindCSS** (styling), **Framer Motion** (animations), **React Markdown** (render bolding/markdown safely), **Axios** (HTTP).
- **Poetry 2.x** (`package-mode=false`) for clean dependency management in Docker.
- **Docker (multi-stage)** to build the SPA and run backend in one container.

---

## 🧪 Example Requests

### `POST /chat`

Body:

```json
{
  "query": "a dystopian story about surveillance and freedom",
  "k": 3
}
```

Response (shape):

```json
{
  "query": "...",
  "chosen_title": "Fahrenheit 451",
  "answer": "Short reason + full stored summary...",
  "context_used": [
    {"title":"Fahrenheit 451","themes":["freedom","surveillance","..."]},
    ...
  ]
}
```

### `POST /tts`

Body:

```json
{
  "text": "The book is ...",
  "voice": "alloy"
}
```

Response: `audio/mpeg` (MP3 bytes).

> The front-end fetches this as `arraybuffer`, then plays via `<audio>`.

---

## 🧷 Moderation (optional)

Backend includes a helper like:

```python
def is_clean(user_query: str) -> bool:
    r = client.moderations.create(model="omni-moderation-latest", input=user_query)
    return not bool(r.results[0].flagged)
```

- If flagged → decline with a safe message (in the user’s language).
- You can place this check near the top of `/chat`.

---

## 🛠 Local Development (optional)

If you want to dev without Docker:

**Backend**

```bash
# from backend/
poetry install
# set OPENAI_API_KEY in your shell or backend/.env (local only)
uvicorn api:app --reload --port 8000
```

**Frontend**

```bash
# from frontend/
npm install
npm run dev
```

If you run frontend at `5173` and backend at `8000`, enable CORS in FastAPI for local dev (Docker doesn’t need it).

---

## 🐳 Docker Image Notes

- **Multi-stage**: Node builds React → Python serves the static `frontend_dist` folder via FastAPI:

  ```python
  from fastapi.staticfiles import StaticFiles
  dist_dir = Path(__file__).parent.parent / "frontend_dist"
  app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")
  ```

- **No secrets** in image: `OPENAI_API_KEY` is injected at runtime by Compose (`environment:`).
- **Persistence**: Chroma store `.chroma/` is a named Docker volume (`chroma_data`).

---

## 🧯 Troubleshooting

- **“Repository not found” on push**: verify `git remote -v` and your GitHub auth (`ssh -T git@github.com` or HTTPS token).
- **401 Invalid API key**: check `/health` output; ensure your Docker shell has `OPENAI_API_KEY` set or root `.env` exists.
- **`/tts` plays nothing**: front-end must request `arraybuffer` and set `audio.src = URL.createObjectURL(new Blob([data], { type: 'audio/mpeg' }))`.
- **`/debug/search` empty**: did you run `scripts/ingest_chroma.py`? Ensure it sees your JSON data (`data/book_summaries.json`) and the same embedding model.
