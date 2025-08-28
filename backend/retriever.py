from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI
import chromadb
import os
from pathlib import Path

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
COLLECTION = "books"


class BookRetriever:
    def __init__(self):
        backend_root = Path(__file__).resolve().parent
        chroma_dir = os.getenv("CHROMA_DIR", ".chroma")
        chroma_path = (backend_root / chroma_dir).resolve()

        print(f"[retriever] CHROMA_DIR={chroma_dir} -> {chroma_path}")
        print(f"[retriever] COLLECTION={COLLECTION}")

        self.client_oai = OpenAI()
        self.client_ch = chromadb.PersistentClient(path=str(chroma_path))

        self.coll = self.client_ch.get_or_create_collection(
            name=COLLECTION, metadata={"hnsw:space": "cosine"}
        )
        try:
            c = self.coll.count()
            print(f"[retriever] collection count = {c}")
        except Exception as e:
            print("[retriever] failed to count collection:", e)

    def search(self, query: str, k: int = 3) -> List[Dict]:
        # 1) embed the query with the SAME model used at ingestion
        q = (
            self.client_oai.embeddings.create(model=EMBED_MODEL, input=[query])
            .data[0]
            .embedding
        )

        # 2) query Chroma
        res = self.coll.query(
            query_embeddings=[q],
            n_results=k,
            include=["distances", "metadatas", "documents"],
        )

        hits = []
        for idx, meta in enumerate(res.get("metadatas", [[]])[0]):
            dist = res["distances"][0][idx]  # cosine distance
            score = 1 - dist  # convert to similarity-ish
            themes_str = meta.get("themes")  # stored as comma-separated string
            themes = (
                [t.strip() for t in themes_str.split(",")]
                if isinstance(themes_str, str)
                else []
            )
            hits.append(
                {
                    "id": res["ids"][0][idx],
                    "score": round(float(score), 4),
                    "title": meta.get("title"),
                    "themes": themes,
                    "summary": meta.get("summary"),
                    "document": res["documents"][0][idx],
                }
            )
        hits.sort(key=lambda x: x["score"], reverse=True)
        return hits

    def list_titles(self) -> list[str]:
        """Return all titles stored in the collection (small dataset => OK)."""
        records = self.coll.get(include=["metadatas"])
        metas = records.get("metadatas", [])
        titles = []
        for m in metas:
            if isinstance(m, list):
                for mm in m:
                    t = (mm or {}).get("title")
                    if t:
                        titles.append(t)
            else:
                t = (m or {}).get("title")
                if t:
                    titles.append(t)
        return titles

    def get_summary_by_title(self, title: str) -> dict:
        """
        Return the stored summary & metadata for an exact book title.
        Tries exact match first; if not found, does a case-insensitive fallback scan.
        """
        try:
            res = self.coll.get(
                where={"title": {"$eq": title}},
                include=["metadatas", "documents", "ids"],
                limit=1,
            )
            if res and res.get("metadatas"):
                meta = res["metadatas"][0]
                doc = res["documents"][0] if res.get("documents") else None
                themes_str = meta.get("themes")
                themes = (
                    [t.strip() for t in themes_str.split(",")]
                    if isinstance(themes_str, str)
                    else []
                )
                return {
                    "found": True,
                    "id": res["ids"][0],
                    "title": meta.get("title"),
                    "summary": meta.get("summary"),
                    "themes": themes,
                    "document": doc,
                }
        except Exception:
            pass

        try:
            all_res = self.coll.get(
                include=["metadatas", "documents", "ids"], limit=1000
            )
            metas = all_res.get("metadatas", [])
            ids = all_res.get("ids", [])
            docs = all_res.get("documents", [])
            t_norm = title.strip().casefold()
            for i, m in enumerate(metas):
                m_title = (m.get("title") or "").strip()
                if m_title.casefold() == t_norm:
                    themes_str = m.get("themes")
                    themes = (
                        [t.strip() for t in themes_str.split(",")]
                        if isinstance(themes_str, str)
                        else []
                    )
                    return {
                        "found": True,
                        "id": ids[i],
                        "title": m_title,
                        "summary": m.get("summary"),
                        "themes": themes,
                        "document": docs[i] if i < len(docs) else None,
                    }
        except Exception:
            pass

        return {"found": False}
