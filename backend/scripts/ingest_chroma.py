import json, re, math
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI
import chromadb
import os

load_dotenv()

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DATA_PATH = REPO_ROOT / "data" / "book_summaries.json"
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", ".chroma"))
CHROMA_PATH = (BACKEND_ROOT / CHROMA_DIR).resolve()

EMBED_MODEL = "text-embedding-3-small"
COLLECTION = "books"
BATCH_SIZE = 128

client_oai = OpenAI()


def slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "untitled"


def load_items() -> List[Dict]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data, f"No items found in {DATA_PATH}"
    items = []
    seen = set()
    for it in data:
        t = str(it.get("title", "")).strip()
        s = str(it.get("summary", "")).strip()
        themes = it.get("themes", [])
        if not t or not s or not isinstance(themes, list):
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "title": t,
                "summary": s,
                "themes": [str(x).strip().lower() for x in themes],
            }
        )
    return items


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Call OpenAI embeddings in batches."""
    out: List[List[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        resp = client_oai.embeddings.create(model=EMBED_MODEL, input=batch)
        out.extend([d.embedding for d in resp.data])
    return out


def main():
    print("Reading:", DATA_PATH.resolve())
    items = load_items()
    print(f"Loaded {len(items)} books")

    docs = []
    metas = []
    ids = []
    for it in items:
        title = it["title"]
        summary = it["summary"]
        themes = ", ".join(it["themes"])
        doc = f"Title: {title}\nSummary: {summary}\nThemes: {themes}"
        docs.append(doc)
        themes_list = [str(x).strip().lower() for x in it["themes"]]
        metas.append(
            {
                "title": title,
                "summary": summary,
                "themes": ", ".join(themes_list),
            }
        )
        ids.append(slugify(title))

    print(f"Embedding {len(docs)} docs with {EMBED_MODEL} ...")
    embs = embed_texts(docs)
    assert len(embs) == len(docs)

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    print("Chroma path:", CHROMA_PATH)
    client_chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))
    coll = client_chroma.get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )

    print(f"Upserting into collection '{COLLECTION}' ...")
    coll.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
    print("Done. Collection size now:", coll.count())


if __name__ == "__main__":
    main()
