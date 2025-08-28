import json, time, re
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = DATA_DIR / "book_summaries.json"
BACKEND_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = BACKEND_ROOT / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

NUM_BOOKS = 50
BATCH_SIZE = 5
TEMPERATURE = 0.7

SEED_BUCKETS = [
    "friendship, adventure, courage",
    "freedom, control, surveillance",
    "love, loss, redemption",
    "coming of age, identity, belonging",
    "mystery, justice, morality",
]

PROMPT_TMPL = """You are generating entries about real, well-known books.

Rules:
- Return ONLY valid JSON (no prose, no commentary).
- Format: a JSON array of objects.
- Each object must have:
  - "title": the exact, real published book title (3-7 words if possible)
  - "summary": 2-5 sentences (~60-120 words total), a concise original description in your own words
  - "themes": array of 2-5 short lowercase phrases that capture the book’s main themes

Do not invent books. Only include widely known real books from world literature, science, philosophy, or other fields.
Avoid spoilers in summaries.

Now create {n} real book entries with these thematic cues:
{cues}
"""


def normalize_title(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip())


def validate_item(it: dict) -> bool:
    if not isinstance(it, dict):
        return False
    if not all(k in it for k in ("title", "summary", "themes")):
        return False
    title = normalize_title(str(it["title"]))
    wc = len(title.split())
    if not (2 <= wc <= 10):
        return False
    if len(re.findall(r"[.!?]", str(it["summary"]))) < 1:
        return False
    themes = it["themes"]
    if not isinstance(themes, list) or not (2 <= len(themes) <= 5):
        return False
    return True


def parse_json_safely(text: str):
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        text = text.replace("json", "", 1).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    (TMP_DIR / "bad_output.json").write_text(text, encoding="utf-8")
    raise RuntimeError(
        "Model did not return parseable JSON. See backend/tmp/bad_output.json"
    )


def ask_llm(n: int, cues: str, batch_index: int):
    prompt = PROMPT_TMPL.format(n=n, cues=cues)
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        temperature=TEMPERATURE,
        max_output_tokens=1500,
        stream=False,
    )
    text = (resp.output_text or "").strip()

    (TMP_DIR / f"raw_batch_{batch_index}.txt").write_text(text, encoding="utf-8")

    data = parse_json_safely(text)

    (TMP_DIR / f"parsed_batch_{batch_index}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data


def main():
    print("Repo root:", REPO_ROOT)
    print("Writing to:", OUT_PATH.resolve())
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_items: List[Dict] = []
    seen_titles = set()

    num_batches = (NUM_BOOKS + BATCH_SIZE - 1) // BATCH_SIZE
    buckets = (
        SEED_BUCKETS * ((num_batches + len(SEED_BUCKETS) - 1) // len(SEED_BUCKETS))
    )[:num_batches]

    for i, cue in enumerate(buckets, start=1):
        batch_raw = ask_llm(BATCH_SIZE, cue, i)
        if not isinstance(batch_raw, list):
            print(f"Batch {i}: parsed shape was not a list; skipping.")
            continue

        cleaned = []
        for it in batch_raw:
            if not validate_item(it):
                continue
            it["title"] = normalize_title(it["title"])
            key = it["title"].lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            cleaned.append(
                {
                    "title": it["title"],
                    "summary": str(it["summary"]).strip(),
                    "themes": [str(x).strip().lower() for x in it["themes"]],
                }
            )

        print(
            f"Batch {i}: received {len(batch_raw)}, kept {len(cleaned)}; total so far {len(all_items)+len(cleaned)}"
        )

        all_items.extend(cleaned)
        if len(all_items) >= NUM_BOOKS:
            break

        time.sleep(0.3)

    all_items = all_items[:NUM_BOOKS]
    OUT_PATH.write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ Wrote {len(all_items)} items to {OUT_PATH.resolve()}")
    if len(all_items) < NUM_BOOKS:
        print(
            "Note: fewer items than requested — inspect files under backend/tmp/ to see why."
        )


if __name__ == "__main__":
    main()
