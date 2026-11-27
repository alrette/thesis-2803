"""
Prepare a self-contained Spider data bundle for `deploy/backend/data/`.

What it does:
  1. Inspects all Spider dev databases in `--spider-dir` and ranks them by schema
     richness (table count, FK count, column count), or uses `--dbs` if provided.
  2. Copies the chosen `.sqlite` files into `deploy/backend/data/databases/<db_id>/`.
  3. Writes a filtered `deploy/backend/data/tables.json` for just those DBs.
  4. Curates diverse sample questions from Spider `dev.json` into `deploy/backend/data/catalog.json`.
  5. Copies `data/skeletons/train.json` from the thesis repo into `deploy/backend/data/skeletons/train.json`.
  6. Optionally (`--precompute-embeddings`) encodes all training skeletons with
     `BAAI/bge-m3` into `train_embeddings.npy` (~14 MB float16) for fast HF Spaces startup.

Usage:
    python scripts/prepare_spider_bundle.py --spider-dir ../../data/spider_data --top-n 6 --precompute-embeddings
    python scripts/prepare_spider_bundle.py --spider-dir /path/to/spider_data --dbs student_transcripts_tracking car_1 dog_kennels world_1 flight_2 concert_singer
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
THESIS_ROOT = BACKEND_DIR.parents[1]
DEFAULT_OUT = BACKEND_DIR / "data"
DEFAULT_TRAIN_SKELETONS = THESIS_ROOT / "data" / "skeletons" / "train.json"

# Friendly descriptions for common rich Spider dev databases
KNOWN_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "student_transcripts_tracking": (
        "Student Transcripts & Courses",
        "University degrees, departments, courses, student enrollments, semesters, and transcript records.",
    ),
    "cre_Doc_Template_Mgt": (
        "Document Template Management",
        "Templates, document versions, paragraphs, and reference template types.",
    ),
    "dog_kennels": (
        "Dog Kennels & Treatments",
        "Dogs, owners, breeds, sizes, professionals, treatments, and service charges.",
    ),
    "car_1": (
        "Car Makers & Models",
        "Continents, countries, car manufacturers, model lists, and vehicle performance specs.",
    ),
    "world_1": (
        "World Countries & Cities",
        "Countries, cities, official languages, population, and macroeconomic indicators.",
    ),
    "flight_2": (
        "Airlines, Airports & Flights",
        "Airlines, airport locations, and scheduled flight routes.",
    ),
    "concert_singer": (
        "Concerts & Singers",
        "Stadiums, singers, concert events, and performer lineups.",
    ),
    "orchestra": (
        "Orchestra & Performances",
        "Conductors, orchestras, performances, and show attendance.",
    ),
    "network_1": (
        "High School Social Network",
        "High schoolers, friendships, and likes graph.",
    ),
    "tvshow": (
        "TV Channels & Cartoons",
        "TV channels, series schedules, and cartoon episodes.",
    ),
    "real_estate_properties": (
        "Real Estate Properties",
        "Property types, listings, features, and reference catalogs.",
    ),
    "course_teach": (
        "Courses & Teachers",
        "Teachers, courses, and course teaching assignments.",
    ),
    "wta_1": (
        "WTA Tennis Matches",
        "Tennis players, rankings, and tournament match results.",
    ),
}


def _humanize_db_name(db_id: str) -> str:
    if db_id in KNOWN_DESCRIPTIONS:
        return KNOWN_DESCRIPTIONS[db_id][0]
    cleaned = re.sub(r"_\d+$", "", db_id).replace("_", " ")
    return cleaned.title()


def _sql_complexity_bucket(sql: str) -> str:
    upper = sql.upper()
    joins = len(re.findall(r"\bJOIN\b", upper))
    has_subquery = len(re.findall(r"\bSELECT\b", upper)) > 1
    has_set_op = any(op in upper for op in ("INTERSECT", "EXCEPT", "UNION"))
    has_group = "GROUP BY" in upper or "HAVING" in upper
    if has_subquery or has_set_op or joins >= 2:
        return "Hard"
    if joins == 1 or has_group:
        return "Medium"
    return "Easy"


def _pick_sample_questions(items: list[dict], limit: int = 6) -> list[dict]:
    """Pick diverse questions (distinct gold SQL, balanced Easy/Medium/Hard)."""
    seen_sql: set[str] = set()
    by_bucket: dict[str, list[dict]] = defaultdict(list)

    for item in items:
        norm_sql = re.sub(r"\s+", " ", item["query"].strip().lower())
        if norm_sql in seen_sql:
            continue
        seen_sql.add(norm_sql)
        bucket = _sql_complexity_bucket(item["query"])
        by_bucket[bucket].append(
            {
                "question": item["question"].strip(),
                "difficulty": bucket,
            }
        )

    selected: list[dict] = []
    # Round-robin Easy -> Medium -> Hard so users can try simple and multi-table queries
    buckets = ("Easy", "Medium", "Hard")
    idx = {b: 0 for b in buckets}
    while len(selected) < limit:
        added = False
        for b in buckets:
            if idx[b] < len(by_bucket[b]) and len(selected) < limit:
                selected.append(by_bucket[b][idx[b]])
                idx[b] += 1
                added = True
        if not added:
            break
    return selected


def precompute_train_embeddings(train_sk_path: Path, out_npy: Path, model_name: str) -> None:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    rows = json.loads(train_sk_path.read_text(encoding="utf-8"))
    texts = [r["skeleton"] for r in rows]
    print(f"Encoding {len(texts)} training skeletons with {model_name} ...")
    model = SentenceTransformer(model_name)
    emb = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        batch_size=256,
        show_progress_bar=True,
    )
    out_npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(out_npy, emb.astype(np.float16))
    size_mb = out_npy.stat().st_size / (1024 * 1024)
    print(f"Saved precomputed embeddings -> {out_npy} ({emb.shape}, {size_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Curate richer Spider dev DBs for deployment.")
    parser.add_argument("--spider-dir", type=Path, required=True, help="Path to spider_data/")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT, help="Output backend data dir")
    parser.add_argument("--top-n", type=int, default=6, help="How many richest dev DBs to include")
    parser.add_argument("--dbs", nargs="+", default=None, help="Explicit list of Spider db_ids")
    parser.add_argument("--questions-per-db", type=int, default=6, help="Sample questions per DB")
    parser.add_argument("--max-db-mb", type=float, default=35.0, help="Skip .sqlite files larger than this")
    parser.add_argument(
        "--train-skeletons",
        type=Path,
        default=DEFAULT_TRAIN_SKELETONS,
        help="Path to data/skeletons/train.json",
    )
    parser.add_argument(
        "--precompute-embeddings",
        action="store_true",
        help="Precompute BGE-M3 float16 embeddings for train skeletons (.npy)",
    )
    parser.add_argument("--embedding-model", type=str, default="BAAI/bge-m3")
    args = parser.parse_args()

    tables_all = json.loads((args.spider_dir / "tables.json").read_text(encoding="utf-8"))
    dev_all = json.loads((args.spider_dir / "dev.json").read_text(encoding="utf-8"))
    db_root = args.spider_dir / "database"

    dev_by_db: dict[str, list[dict]] = defaultdict(list)
    for row in dev_all:
        dev_by_db[row["db_id"]].append(row)

    tables_by_db = {db["db_id"]: db for db in tables_all}

    # Rank dev DBs by schema richness (table count, FK count, column count)
    ranked = []
    for db_id, items in dev_by_db.items():
        if db_id not in tables_by_db:
            continue
        sqlite_path = db_root / db_id / f"{db_id}.sqlite"
        if not sqlite_path.exists():
            continue
        size_mb = sqlite_path.stat().st_size / (1024 * 1024)
        if args.dbs is None and size_mb > args.max_db_mb:
            continue
        schema = tables_by_db[db_id]
        n_tables = len(schema["table_names_original"])
        n_cols = len(schema["column_names_original"]) - 1  # exclude '*'
        n_fks = len(schema["foreign_keys"])
        ranked.append((n_tables, n_fks, n_cols, db_id, size_mb))

    ranked.sort(reverse=True)
    print("\nTop Spider dev databases by schema richness:")
    for n_t, n_fk, n_c, db_id, size_mb in ranked[:12]:
        print(f"  {db_id:32s} | tables={n_t:2d} | fks={n_fk:2d} | cols={n_c:3d} | {size_mb:5.2f} MB")

    if args.dbs:
        chosen_ids = args.dbs
    else:
        chosen_ids = [row[3] for row in ranked[: args.top_n]]

    out_db_dir = args.out_dir / "databases"
    if out_db_dir.exists():
        shutil.rmtree(out_db_dir)
    out_db_dir.mkdir(parents=True, exist_ok=True)

    curated_tables = []
    catalog_entries = []

    for db_id in chosen_ids:
        if db_id not in tables_by_db:
            raise ValueError(f"db_id '{db_id}' not found in tables.json")
        src_sqlite = db_root / db_id / f"{db_id}.sqlite"
        if not src_sqlite.exists():
            raise FileNotFoundError(f"SQLite file missing: {src_sqlite}")

        dst_dir = out_db_dir / db_id
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_sqlite, dst_dir / f"{db_id}.sqlite")

        curated_tables.append(tables_by_db[db_id])
        samples = _pick_sample_questions(dev_by_db.get(db_id, []), limit=args.questions_per_db)
        desc = KNOWN_DESCRIPTIONS.get(
            db_id,
            (_humanize_db_name(db_id), f"Spider benchmark database ({db_id}) with multi-table relations."),
        )[1]
        catalog_entries.append(
            {
                "db_id": db_id,
                "display_name": _humanize_db_name(db_id),
                "description": desc,
                "sample_questions": samples,
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "tables.json").write_text(
        json.dumps(curated_tables, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (args.out_dir / "catalog.json").write_text(
        json.dumps({"databases": catalog_entries}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Copy train skeletons for skeleton few-shot
    dst_sk_dir = args.out_dir / "skeletons"
    dst_sk_dir.mkdir(parents=True, exist_ok=True)
    dst_train_sk = dst_sk_dir / "train.json"
    if args.train_skeletons.exists():
        shutil.copy2(args.train_skeletons, dst_train_sk)
        print(f"\nCopied train skeletons -> {dst_train_sk}")
    else:
        print(f"\nWARNING: {args.train_skeletons} not found; few-shot k>0 needs train.json")

    if args.precompute_embeddings and dst_train_sk.exists():
        precompute_train_embeddings(
            dst_train_sk,
            dst_sk_dir / "train_embeddings.npy",
            args.embedding_model,
        )

    print(f"\nDone! Curated {len(chosen_ids)} databases into {args.out_dir}: {chosen_ids}")


if __name__ == "__main__":
    main()
