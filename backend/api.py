# backend/api.py
from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv, dotenv_values
from openai import OpenAI
from fastapi.responses import StreamingResponse
import io
import re
import os, json, re, traceback
from retriever import BookRetriever

# ------------------ App & deps ------------------
load_dotenv()
app = FastAPI(title="Smart Librarian (Responses API)")
client = OpenAI()
retriever = None
init_error = None
MAX_TTS_CHARS = 1800

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    retriever = BookRetriever()
except Exception as e:
    init_error = f"{type(e).__name__}: {e}"
    print("[api] Failed to init BookRetriever:", init_error)
    print(traceback.format_exc())


# ------------------ Models ------------------
class ChatRequest(BaseModel):
    query: str
    k: int = 3


# ------------------ Helpers ------------------
def build_context(hits: list[dict]) -> str:
    """Compact block the model can reliably scan."""
    lines = []
    for i, h in enumerate(hits, start=1):
        themes = ", ".join(h.get("themes", []))
        lines.append(
            f"{i}. Title: {h['title']}\n   Themes: {themes}\n   Summary: {h['summary']}"
        )
    return "\n\n".join(lines)


def parse_json_object(text: str) -> dict:
    """
    Parse the model's 'JSON-only' reply.
    Accepts:
      - raw object
      - fenced ```json blocks
      - first { ... } block via regex
      - single-element array of object
    """
    t = (text or "").strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].replace("json", "", 1).strip()
    try:
        data = json.loads(t)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError("Model did not return parseable JSON")


def detect_language_iso(query: str) -> str:
    """
    Return a strict ISO 639-1 code ('en', 'ro', 'es', ...).
    Falls back to 'en' if the model is uncertain.
    """
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=(
            "Return ONLY the two-letter ISO 639-1 language code of the USER QUERY text.\n"
            "If uncertain, return 'en'.\n\n"
            f"USER QUERY: {query}"
        ),
        temperature=0.0,
        max_output_tokens=16,
        stream=False,
    )
    raw = (resp.output_text or "en").strip().lower()

    m = re.search(r"[a-z]{2}", raw)
    return m.group(0) if m else "en"


def same_language_rewrite(user_query: str, base_text: str, force_lang_name: str) -> str:
    """
    Rewrites/outputs `base_text` in `force_lang_name` with NO shortening.
    We forbid summaries, keep examples verbatim, and return plain text only.
    """
    prompt = (
        f"Return the following message in {force_lang_name}.\n"
        "Rules:\n"
        "- Preserve ALL content and examples exactly; do NOT shorten or summarize.\n"
        "- Keep punctuation and parenthetical examples intact.\n"
        "- Do not add headings or extra labels. Return PLAIN TEXT only.\n\n"
        f"MESSAGE:\n{base_text}"
    )

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        temperature=0.0,  # deterministic; avoids creative shortening
        max_output_tokens=800,  # plenty of room so it won't truncate
        stream=False,
    )
    return (resp.output_text or "").strip()


def is_clean(user_query: str) -> bool:
    """
    Uses OpenAI's hosted moderation model (omni-moderation-latest).
    Returns True if the text is OK, False if flagged.
    """
    text = (user_query or "").strip()
    if not text:
        return True
    try:
        r = client.moderations.create(model="omni-moderation-latest", input=text)
        return not bool(r.results[0].flagged)
    except Exception:
        # If moderation API fails, allow by default (or set to False to block)
        return True


def classify_query(query: str) -> dict:
    """
    Classify if the query is about books/themes/vibes and extract any named entity.
    Returns JSON like:
    {
      "intent": "book_request" | "chit_chat" | "other",
      "named_entity": {"text": "...", "type": "title|author|person|none"},
      "must_exact_match": true|false,   # if true, don't recommend substitutes
      "reason": "short explanation"
    }
    """
    prompt = (
        "You are a strict classifier for a book recommender.\n"
        "Return ONLY JSON.\n"
        "Decide:\n"
        "- intent: 'book_request' if the user asks for a book recommendation, a theme, vibe, genre, summary, author/title search, etc.\n"
        "- intent: 'chit_chat' for greetings/small talk/personal questions.\n"
        "- intent: 'other' for anything else.\n"
        "- named_entity: extract a single explicit person/author/title mentioned, else 'none'.\n"
        "- must_exact_match: true if the user asks ABOUT a specific real person/author/title (e.g. 'a book about Michelle Obama', 'Find \"Dune\"'), false otherwise.\n"
        "Example outputs:\n"
        '{ "intent":"chit_chat", "named_entity":{"text":"","type":"none"}, "must_exact_match":false, "reason":"greeting" }\n'
        '{ "intent":"book_request", "named_entity":{"text":"Michelle Obama","type":"person"}, "must_exact_match":true, "reason":"specific person requested" }\n'
        '{ "intent":"book_request", "named_entity":{"text":"","type":"none"}, "must_exact_match":false, "reason":"theme request" }\n'
        "\nUSER QUERY:\n"
        f"{query}\n"
        "\nReturn JSON only."
    )
    r = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        temperature=0.0,
        max_output_tokens=300,
        stream=False,
    )
    text = (r.output_text or "").strip()
    try:
        return parse_json_object(text)
    except Exception:
        return {
            "intent": "other",
            "named_entity": {"text": "", "type": "none"},
            "must_exact_match": False,
            "reason": "parser_fallback",
        }


def _tts_stream_bytes(text: str, voice: str = "alloy"):
    try:
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text,
        ) as resp:
            for chunk in resp.iter_bytes():
                yield chunk
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")


# ------------------ Health & debug ------------------


@app.get("/health")
def health():
    env_val = os.getenv("OPENAI_API_KEY")
    dotenv_path = find_dotenv(usecwd=True)
    dotenv_vals = dotenv_values(dotenv_path) if dotenv_path else {}
    dotenv_has_key = "OPENAI_API_KEY" in dotenv_vals
    dotenv_preview = (
        (dotenv_vals.get("OPENAI_API_KEY") or "")[:7] + "…" if dotenv_has_key else None
    )

    if dotenv_has_key and env_val and dotenv_vals.get("OPENAI_API_KEY") == env_val:
        source = f".env ({dotenv_path})"
    elif dotenv_has_key and not env_val:
        source = f".env only ({dotenv_path})"
    else:
        source = "process environment (user/system/VSCode envFile)"

    return {
        "status": "ok",
        "key_present": bool(env_val),
        "key_preview": (env_val[:7] + "…") if env_val else None,
        "len": len(env_val) if env_val else 0,
        "source_guess": source,
        "dotenv_path": dotenv_path or None,
        "dotenv_has_key": dotenv_has_key,
        "dotenv_preview": dotenv_preview,
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    }


@app.get("/debug/search")
def debug_search(q: str = Query(...), k: int = 3):
    if retriever is None:
        raise HTTPException(status_code=500, detail="Retriever not initialized.")
    hits = retriever.search(q, k=k)
    return {
        "query": q,
        "results": [
            {"title": h["title"], "score": h["score"], "themes": h["themes"]}
            for h in hits
        ],
    }


# ------------------ CHAT (RAG + server-side 'tool' + guardrails) ------------------


@app.post("/chat")
def chat(req: ChatRequest = Body(...)):
    if retriever is None:
        raise HTTPException(status_code=500, detail="Retriever not initialized.")
    if not is_clean(req.query):
        return {
            "query": req.query,
            "chosen_title": None,
            "answer": "⚠️ Please use respectful language. I can only help with book-related queries.",
            "context_used": [],
        }

    lang_code = detect_language_iso(req.query)
    LANG_CODE_TO_NAME = {
        "en": "English",
        "ro": "Romanian",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
    }
    lang_name = LANG_CODE_TO_NAME.get(lang_code, "English")

    # ---------------- Guardrail A: classify intent ----------------
    # Only answer if it is a book request (themes/vibes/reading).
    cls_prompt = (
        "You are a strict classifier for a book recommender.\n"
        "Return ONLY JSON.\n"
        "Decide:\n"
        "- intent: 'book_request' if the user asks for a book recommendation, a theme/vibe/genre, summary, "
        "or mentions an author/title in a way that implies a request for a book.\n"
        "- intent: 'chit_chat' for greetings/small talk/personal questions.\n"
        "- intent: 'other' for anything else.\n"
        "- named_entity: extract a single explicit person/author/title mentioned, else 'none'.\n"
        "- must_exact_match: true if the user asks ABOUT a specific real person/author/title (e.g., 'a book about Michelle Obama', 'Find \"Dune\"').\n"
        "Example outputs:\n"
        '{ "intent":"chit_chat", "named_entity":{"text":"","type":"none"}, "must_exact_match":false, "reason":"greeting" }\n'
        '{ "intent":"book_request", "named_entity":{"text":"Michelle Obama","type":"person"}, "must_exact_match":true, "reason":"specific person requested" }\n'
        '{ "intent":"book_request", "named_entity":{"text":"","type":"none"}, "must_exact_match":false, "reason":"theme request" }\n\n'
        f"USER QUERY:\n{req.query}\n\nReturn JSON only."
    )
    try:
        cls_resp = client.responses.create(
            model="gpt-4o-mini",
            input=cls_prompt,
            temperature=0.0,
            max_output_tokens=300,
            stream=False,
        )
        cls = parse_json_object((cls_resp.output_text or "").strip())
    except Exception:
        cls = {
            "intent": "other",
            "named_entity": {"text": "", "type": "none"},
            "must_exact_match": False,
        }

    intent = (cls.get("intent") or "").strip()
    ne = cls.get("named_entity") or {}
    ne_text = (ne.get("text") or "").strip()
    ne_type = (ne.get("type") or "none").strip().lower()
    must_exact = bool(cls.get("must_exact_match"))

    if intent != "book_request":
        decline_en = (
            "I only handle book recommendations based on themes, vibes or titles. "
            "Try: 'a book about friendship and magic' or 'something dystopian but hopeful'."
        )
        decline = same_language_rewrite(
            req.query, decline_en, force_lang_name=lang_name
        )
        return {
            "query": req.query,
            "chosen_title": None,
            "answer": decline,
            "context_used": [],
        }

    # ---------------- Guardrail B: exact-match policy ----------------
    # If user asked for a specific person/title and we don't have it, refuse substitutes.
    import unicodedata, re as _re

    def _norm(s: str) -> str:
        if not s:
            return ""
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        return _re.sub(r"\s+", " ", s).strip().lower()

    def _all_titles() -> set[str]:
        cache = getattr(retriever, "_title_cache", None)
        if cache is not None:
            return cache
        titles: list[str] = []
        try:
            if hasattr(retriever, "list_titles"):
                titles = list(retriever.list_titles() or [])
            else:
                rec = retriever.coll.get(include=["metadatas"]) or {}
                metas = rec.get("metadatas") or []
                for m in metas:
                    if isinstance(m, dict):
                        t = m.get("title")
                        if t:
                            titles.append(t)
                    elif isinstance(m, list):
                        for mm in m:
                            if isinstance(mm, dict) and mm.get("title"):
                                titles.append(mm["title"])
        except Exception:
            titles = []
        cache = set(titles)
        retriever._title_cache = cache
        return cache

    if must_exact and ne_type in {"title", "author", "person"} and ne_text:
        titles_norm = {_norm(t) for t in _all_titles()}
        target = _norm(ne_text)
        has_exact = any(target == t or target in t for t in titles_norm)
        if not has_exact:
            msg_en = (
                f"I can only recommend from the stored collection and I couldn't find an exact match for '{ne_text}'. "
                "Try asking by theme or vibe instead (e.g., 'a memoir about resilience')."
            )
            msg = same_language_rewrite(req.query, msg_en, force_lang_name=lang_name)
            return {
                "query": req.query,
                "chosen_title": None,
                "answer": msg,
                "context_used": [],
            }

    hits = retriever.search(req.query, k=req.k)
    if not hits:
        msg = same_language_rewrite(
            req.query,
            "I couldn’t find relevant matches in the collection.",
            force_lang_name=lang_name,
        )
        return {
            "query": req.query,
            "chosen_title": None,
            "answer": msg,
            "context_used": [],
        }

    context_block = build_context(hits)
    choose_instructions = (
        "You are a helpful book recommender. "
        "From the CONTEXT list, pick exactly one title (MUST be one from the list). "
        "If nothing fits the USER QUERY, return an empty title.\n"
        'Return ONLY JSON: {"title": <exact title or "">, "reason": <one or two sentences>}. '
        f"Write the `reason` in {lang_name}."
    )
    choose_prompt = (
        f"{choose_instructions}\n\n"
        f"USER QUERY: {req.query}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        "Return JSON only."
    )
    pick_text = ""
    chosen_title = ""
    reason = ""
    try:
        pick = client.responses.create(
            model="gpt-4o-mini",
            input=choose_prompt,
            temperature=0.2,
            max_output_tokens=500,
            stream=False,
        )
        pick_text = pick.output_text or ""
        parsed = parse_json_object(pick_text)
        chosen_title = (parsed.get("title") or "").strip()
        reason = (parsed.get("reason") or "").strip()
    except Exception as e:
        print("[/chat] Failed to parse chosen title:", e, "\nRAW:", pick_text)

    if not chosen_title:
        msg = same_language_rewrite(
            req.query,
            "I couldn’t find a suitable match in the collection. Try a different theme or vibe.",
            force_lang_name=lang_name,
        )
        return {
            "query": req.query,
            "chosen_title": None,
            "answer": msg,
            "context_used": [
                {"title": h["title"], "themes": h["themes"]} for h in hits
            ],
        }

    tool_result = retriever.get_summary_by_title(chosen_title)
    if not tool_result.get("found"):
        chosen_title = hits[0]["title"]
        tool_result = retriever.get_summary_by_title(chosen_title)

    compose_instructions = (
        f"Compose a concise recommendation in {lang_name}. "
        "Mention the chosen title once, explain briefly why it fits the query, "
        "then include the full stored summary. Keep it under 150 words."
    )
    compose_prompt = (
        f"{compose_instructions}\n\n"
        f"USER QUERY: {req.query}\n\n"
        f"CHOSEN TITLE: {chosen_title}\n"
        f"REASON: {reason}\n\n"
        f"TOOL RESULT (JSON):\n{json.dumps(tool_result, ensure_ascii=False)}"
    )

    final = client.responses.create(
        model="gpt-4o-mini",
        input=compose_prompt,
        temperature=0.4,
        max_output_tokens=600,
        stream=False,
    )
    final_text = (final.output_text or "").strip()

    return {
        "query": req.query,
        "chosen_title": chosen_title,
        "answer": final_text,
        "context_used": [{"title": h["title"], "themes": h["themes"]} for h in hits],
    }


@app.post("/tts")
def tts_post(body: dict = Body(...)):
    """
    POST { text, voice? } -> audio/mpeg
    """
    text = (body.get("text") or "").strip()
    voice = (body.get("voice") or "alloy").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Field 'text' is required.")
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]

    return StreamingResponse(
        _tts_stream_bytes(text, voice=voice),
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'inline; filename="speech.mp3"'},
    )


# for Postman/testing in browser:
@app.get("/tts")
def tts_get(text: str = Query(..., min_length=1), voice: str = Query("alloy")):
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS]
    return StreamingResponse(
        _tts_stream_bytes(text, voice=voice),
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'inline; filename="speech.mp3"'},
    )
