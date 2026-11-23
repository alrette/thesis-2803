"""
tep_steps.py — langkah-langkah notebooks/eval_tep.ipynb: TEP dengan DAIL-SQL sebagai B (poin 45).

TEP_c = (ΔEX / EX_B) / (ΔT / T_B), Δ = kondisi c − B, dengan B = DAIL-SQL (baseline skripsi) dan
c = GraphRAG 1-Stage atau GraphRAG 2-Stage, per model (3B, 7B, 14B). Rumusnya tetap compute_tep()
di src/metrics/tep.py, dipanggil lewat metrics_summary._tep() yang sama dengan eval_dail.ipynb.
Tidak ada formula baru dan tidak ada run GPU: semua angka dibaca dari hasil run yang sudah disimpan.

Sumber per model dan kondisi (urutan prioritas):
1. Hasil zip yang diekstrak (`hasil_<MODEL>.zip`, `hasil_dail_<MODEL>.zip`): metadata dari
   `tables/metrics_results.json` atau `tables/dail/dail_metrics_results.json`, raw_logs dari folder
   `raw_logs/` di sebelahnya. Model, sampel, dan k few-shot bisa dicek dari metadata.
2. Excel unduhan (`hasil_skripsi_<MODEL>.xlsx`, `hasil_dail_<MODEL>.xlsx`): sheet `Per Query`
   (EX, T_in, T_out per pertanyaan). Metadata tidak ada, jadi k few-shot tidak bisa dicek.

Pemeriksaan sebelum TEP dihitung (kalau gagal, baris itu dilewati dengan alasan, bukan crash):
- model sama (dikelompokkan per ukuran 3B/7B/14B; nama lengkap juga dicek kalau ada metadata),
- pertanyaan sama persis (query_id, db_id, gold SQL), jadi SAMPLE_RATIO dan seed sama,
- run DAIL dengan k = cfg.dail_k_shot (9, baseline skripsi); run ablation k lain tidak dipakai.
k few-shot 1-Stage/2-Stage memang berbeda dengan DAIL (best config masing-masing, poin 43), jadi
hanya ditampilkan. T dihitung ulang dari token_input dan token_output dengan α yang sama untuk semua.
"""

# json untuk membaca dan menulis file JSON
import json
# re untuk mengambil ukuran model dari nama
import re
# Wadah data sederhana
from dataclasses import dataclass, field
# Path untuk lokasi file
from pathlib import Path
# Penanda tipe
from typing import Iterable, Optional

# pandas untuk tabel
import pandas as pd
# openpyxl untuk membaca dan menulis Excel
from openpyxl import Workbook, load_workbook

# Format tabel yang sama dengan eval_pipeline
from src.experiments import result_tables as rt
# Penulis sheet Excel yang sama dengan export_excel.py
from src.experiments.export_excel import Sheet
# Fungsi TEP yang sama dengan eval_dail.ipynb (memanggil compute_tep())
from src.experiments.metrics_summary import RESULTS_FILENAME, _tep

# Pipeline yang dibandingkan dengan DAIL-SQL
PIPELINES = ("baseline", "graphrag")
# Label tampilan, sama dengan eval_pipeline dan eval_dail
LABELS = {"baseline": "1-stage", "graphrag": "2-stage", "dail": "DAIL-SQL"}
# Nama file metrik DAIL (dail_steps.DAIL_METRICS; ditulis ulang supaya modul ini tidak butuh torch)
DAIL_METRICS = "dail_metrics_results.json"
# Nama file raw_logs per kondisi
LOG_FILES = {"baseline": "baseline_log.json", "graphrag": "graphrag_log.json", "dail": "dail_log.json"}
# Folder yang dicari secara default: zip diekstrak ke outputs/models/, Excel unduhan di outputs/tables/
DEFAULT_INPUT_DIRS = (Path("outputs/models"), Path("outputs/tables"))
# Kolom Excel Per Query: {kondisi: akhiran nama kolom}; DAIL tanpa akhiran
EXCEL_SUFFIX = {"baseline": " 1-stage", "graphrag": " 2-stage", "dail": ""}
# Label tingkat kesulitan Excel -> kunci raw_logs
DIFF_KEY = {v: k for k, v in rt.DIFF_LABEL.items()}


# Satu hasil run untuk satu model dan satu kondisi
@dataclass
class Run:
    # Ukuran model, mis. "7B"
    model: str
    # "baseline", "graphrag", atau "dail"
    condition: str
    # File asal (JSON metadata atau Excel)
    source: Path
    # Metadata run; kosong untuk Excel
    meta: dict = field(default_factory=dict)
    # Catatan per pertanyaan: query_id, db_id, gold_sql, difficulty, ex_result, token_input, token_output
    logs: Optional[list] = None
    # Alasan logs tidak bisa dibaca
    problem: str = ""

    # "json" atau "excel"
    @property
    def kind(self) -> str:
        return "excel" if self.source.suffix == ".xlsx" else "json"

    # k few-shot run ini, None kalau tidak diketahui
    @property
    def k(self) -> Optional[int]:
        return (self.meta.get("dail") or {}).get("dail_k_shot") if self.condition == "dail" else self.meta.get("few_shot_k")


# Ukuran model dari nama apa pun ("Qwen/Qwen2.5-Coder-7B-Instruct", "hasil_dail_7B" -> "7B")
def model_size(name: str) -> Optional[str]:
    # Cari angka diikuti B, mis. 7B, 14B, 1.5B
    found = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)B\b", str(name).replace("_", " "))
    # None kalau tidak ada
    return f"{found.group(1)}B" if found else None


# Urutan model: 3B, 7B, 14B
def _size_key(model: str) -> float:
    return float(model[:-1]) if model and model[:-1].replace(".", "").isdigit() else float("inf")


# ---------------------------------------------------------------------------
# Membaca hasil run
# ---------------------------------------------------------------------------

# Membaca raw_logs dan menyimpan hanya field yang dipakai TEP dan pengecekan
def _read_logs(path: Path) -> list:
    # Baca file
    entries = json.loads(path.read_text(encoding="utf-8"))
    # Field yang dipakai
    keep = ("query_id", "db_id", "gold_sql", "difficulty", "ex_result", "token_input", "token_output")
    # Kembalikan catatan ringkas
    return [{k: e.get(k) for k in keep} for e in entries]


# Hasil zip yang diekstrak: metadata JSON + raw_logs di sebelahnya
def _json_runs(root: Path) -> list:
    runs = []
    # 1-Stage dan 2-Stage: <root>/tables/metrics_results.json + <root>/raw_logs/
    for path in sorted(root.rglob(RESULTS_FILENAME)):
        # Metadata run
        meta = json.loads(path.read_text(encoding="utf-8")).get("meta", {})
        # Kedua pipeline ada di file yang sama
        for cond in PIPELINES:
            runs.append(_with_logs(Run(model_size(meta.get("llm_model")), cond, path, meta), path.parent.parent))
    # DAIL-SQL: <root>/tables/dail/dail_metrics_results.json + <root>/raw_logs/
    for path in sorted(root.rglob(DAIL_METRICS)):
        # Metadata run DAIL
        meta = json.loads(path.read_text(encoding="utf-8")).get("meta", {})
        runs.append(_with_logs(Run(model_size(meta.get("llm_model")), "dail", path, meta), path.parent.parent.parent))
    return runs


# Mengisi logs dari <root>/raw_logs/, atau mencatat kenapa tidak bisa
def _with_logs(run: Run, root: Path) -> Run:
    # Lokasi raw_logs di zip hasil
    path = root / "raw_logs" / LOG_FILES[run.condition]
    # Baca kalau ada
    if path.exists():
        run.logs = _read_logs(path)
    else:
        run.problem = f"raw_logs tidak ada: {path}"
    return run


# Excel unduhan: sheet Per Query
def _excel_runs(root: Path) -> list:
    runs = []
    # hasil_skripsi_<MODEL>.xlsx berisi 1-Stage dan 2-Stage
    for path in sorted(root.rglob("hasil_skripsi_*.xlsx")):
        rows = _per_query_rows(path)
        for cond in PIPELINES:
            runs.append(_excel_run(path, cond, rows))
    # hasil_dail_<MODEL>.xlsx = DAIL k = 9; hasil_dail_<MODEL>_k<k>.xlsx = ablation k lain
    for path in sorted(root.rglob("hasil_dail_*.xlsx")):
        k = re.search(r"_k(\d+)$", path.stem)
        run = _excel_run(path, "dail", _per_query_rows(path))
        # k dari nama file (konvensi RUN_NAME di eval_dail.ipynb); None = k bawaan
        run.meta = {"dail": {"dail_k_shot": int(k.group(1)) if k else None}}
        runs.append(run)
    return runs


# Baris tabel Per Query sebagai list of dict; [] kalau sheet tidak ada
def _per_query_rows(path: Path) -> list:
    # Buka read-only supaya cepat
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        # Sheet tidak ada
        if "Per Query" not in wb.sheetnames:
            return []
        header, rows = None, []
        for values in wb["Per Query"].iter_rows(values_only=True):
            # Cari baris header tabel
            if header is None:
                if "Query ID" in values:
                    header = list(values)
                continue
            # Tabel berakhir di baris kosong
            if all(v is None for v in values):
                break
            rows.append(dict(zip(header, values)))
        return rows
    finally:
        wb.close()


# Satu Run dari baris Excel; kolom yang kurang dicatat sebagai masalah
def _excel_run(path: Path, cond: str, rows: list) -> Run:
    run = Run(model_size(path.stem), cond, path)
    # Akhiran nama kolom kondisi ini
    suffix = EXCEL_SUFFIX[cond]
    # Kolom yang dibutuhkan
    needed = ["Query ID", "DB", "Gold SQL", "Difficulty", f"EX{suffix}", f"T_in{suffix}", f"T_out{suffix}"]
    if not rows:
        run.problem = f"sheet 'Per Query' tidak ada atau kosong: {path}"
    elif any(c not in rows[0] for c in needed):
        run.problem = f"kolom {[c for c in needed if c not in rows[0]]} tidak ada di sheet 'Per Query': {path}"
    elif any(r[c] is None for r in rows for c in needed):
        run.problem = f"ada baris {LABELS[cond]} yang kosong di sheet 'Per Query': {path}"
    else:
        run.logs = [{"query_id": r["Query ID"], "db_id": r["DB"], "gold_sql": r["Gold SQL"],
                     "difficulty": DIFF_KEY.get(r["Difficulty"], r["Difficulty"]), "ex_result": int(r[f"EX{suffix}"]),
                     "token_input": r[f"T_in{suffix}"], "token_output": r[f"T_out{suffix}"]} for r in rows]
    return run


# Mencari semua hasil run dan memilih satu per model dan kondisi
def find_runs(input_dirs: Iterable[Path] = DEFAULT_INPUT_DIRS, dail_k: Optional[int] = None) -> tuple[dict, list]:
    """({model: {kondisi: Run}}, catatan). JSON (zip) diutamakan daripada Excel; dua sumber sejenis = dilewati.

    dail_k = k DAIL-SQL baseline skripsi; run DAIL dengan k lain (ablation) diabaikan dengan catatan."""
    found, notes = [], []
    for root in map(Path, input_dirs):
        if not root.exists():
            notes.append(f"Folder tidak ada: {root}")
            continue
        found += _json_runs(root) + _excel_runs(root)
    # Kelompokkan per model dan kondisi
    grouped: dict = {}
    for run in found:
        if run.model is None:
            notes.append(f"Ukuran model tidak dikenali dari {run.source}, dilewati")
            continue
        if run.condition == "dail" and dail_k is not None and run.k is not None and run.k != dail_k:
            notes.append(f"{run.model} DAIL-SQL k = {run.k} (ablation) tidak dipakai sebagai B: {run.source}")
            continue
        grouped.setdefault(run.model, {}).setdefault(run.condition, []).append(run)
    runs: dict = {}
    for model, by_cond in grouped.items():
        for cond, candidates in by_cond.items():
            # Zip (JSON) diutamakan karena metadatanya bisa dicek
            for kind in ("json", "excel"):
                same = [r for r in candidates if r.kind == kind]
                if not same:
                    continue
                if len(same) > 1:
                    notes.append(f"{model} {LABELS[cond]}: ditemukan {len(same)} hasil ({', '.join(str(r.source) for r in same)}); "
                                 "sisakan satu, kondisi ini dilewati")
                else:
                    runs.setdefault(model, {})[cond] = same[0]
                    unused = [r for r in candidates if r.kind != kind]
                    if unused:
                        notes.append(f"{model} {LABELS[cond]}: memakai {same[0].source}, bukan {unused[0].source}")
                break
    return dict(sorted(runs.items(), key=lambda kv: _size_key(kv[0]))), notes


# ---------------------------------------------------------------------------
# Pengecekan dan TEP
# ---------------------------------------------------------------------------

# Alasan run DAIL tidak bisa dipakai sebagai B, atau "" kalau bisa
def _dail_problem(model: str, dail: Optional[Run], dail_k: int) -> str:
    if dail is None:
        return f"hasil DAIL-SQL belum ada (jalankan eval_dail.ipynb, ekstrak hasil_dail_{model}.zip)"
    if dail.logs is None:
        return f"DAIL-SQL: {dail.problem}"
    # Excel tanpa akhiran _k = k bawaan
    if dail.k is not None and dail.k != dail_k:
        return f"run DAIL-SQL k = {dail.k} adalah ablation, bukan baseline skripsi (k = {dail_k})"
    return ""


# Alasan pasangan pipeline-DAIL tidak sebanding, atau "" kalau sebanding
def _pair_problem(run: Run, dail: Run) -> str:
    # Nama model lengkap, kalau kedua metadata ada
    a, b = run.meta.get("llm_model"), dail.meta.get("llm_model")
    if a and b and a != b:
        return f"model berbeda: {a} vs {b}"
    # Pertanyaan harus sama persis
    keys = lambda logs: sorted((e["query_id"], e["db_id"], e["gold_sql"]) for e in logs)
    if keys(run.logs) != keys(dail.logs):
        return (f"pertanyaan berbeda ({len(run.logs)} vs {len(dail.logs)} query): SAMPLE_RATIO/seed harus sama "
                "dengan run DAIL-SQL")
    return ""


# Peringatan yang tidak membatalkan TEP
def _warnings(run: Run, dail: Run) -> list:
    out = []
    for r in (run, dail):
        if r.kind == "json" and r.meta.get("is_full_run") is False:
            out.append(f"{LABELS[r.condition]}: run percobaan (SAMPLE_RATIO = {r.meta.get('sample_ratio')})")
        if r.kind == "excel":
            out.append(f"{LABELS[r.condition]}: dari Excel, k few-shot dan model lengkap tidak bisa dicek")
    return out


# Tabel TEP: satu baris per model x pipeline, B = DAIL-SQL
def tep_rows(runs: dict, alpha: float, dail_k: int, models: Iterable[str] = ()) -> list:
    """models = model yang diharapkan (mis. 3B/7B/14B); yang belum punya hasil tetap dapat baris berstatus skipped."""
    rows = []
    for model in sorted(set(models) | set(runs), key=_size_key):
        by_cond = runs.get(model, {})
        dail = by_cond.get("dail")
        dail_problem = _dail_problem(model, dail, dail_k)
        for cond in PIPELINES:
            run = by_cond.get(cond)
            row = {"Model": model, "Pipeline": LABELS[cond], "B": LABELS["dail"], "Status": "skipped",
                   "Few-shot k": run.k if run else None, "DAIL k": dail.k if dail else None,
                   "Source pipeline": str(run.source) if run else "", "Source DAIL": str(dail.source) if dail else ""}
            # Hasil pipeline belum ada atau rusak
            if run is None or run.logs is None:
                row["Note"] = run.problem if run else f"hasil {LABELS[cond]} belum ada (ekstrak hasil_{model}.zip)"
            elif dail_problem:
                row["Note"] = dail_problem
            elif (problem := _pair_problem(run, dail)):
                row["Note"] = problem
            else:
                # Angka mentah dulu (EX, T), baru TEP (urutan guide Dimensi 1)
                ex_b, ex_c = (sum(e["ex_result"] for e in logs) / len(logs) for logs in (dail.logs, run.logs))
                t_b, t_c = (sum(rt._t(e, alpha) for e in logs) / len(logs) for logs in (dail.logs, run.logs))
                # Fungsi yang sama dengan eval_dail.ipynb: B = DAIL, kondisi = pipeline
                tep = _tep(dail.logs, run.logs, alpha)
                # Alasan TEP tidak terdefinisi (kalau ada) dan peringatan
                notes = ([tep["reason"]] if "reason" in tep else []) + _warnings(run, dail)
                row.update({"Status": tep["status"], "Queries": len(run.logs), "EX DAIL-SQL": ex_b, "EX pipeline": ex_c,
                            "ΔEX (pp)": (ex_c - ex_b) * 100, "T DAIL-SQL": t_b, "T pipeline": t_c, "ΔT": t_c - t_b,
                            "Relative ΔT": (t_c - t_b) / t_b if t_b else None, "TEP": tep.get("tep"),
                            "Note": "; ".join(notes)})
            rows.append(row)
    return rows


# Kolom tabel, berurutan
COLUMNS = ["Model", "Pipeline", "B", "Status", "Queries", "EX DAIL-SQL", "EX pipeline", "ΔEX (pp)", "T DAIL-SQL",
           "T pipeline", "ΔT", "Relative ΔT", "TEP", "Few-shot k", "DAIL k", "Note", "Source pipeline", "Source DAIL"]


# Tabel berformat untuk notebook dan Excel
def tep_table(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    return rt.with_formats(df, {"Queries": "int", "EX DAIL-SQL": "pct", "EX pipeline": "pct", "ΔEX (pp)": "pp",
                                "T DAIL-SQL": "num1", "T pipeline": "num1", "ΔT": "dnum1", "Relative ΔT": "rel",
                                "TEP": "num4", "Few-shot k": "int", "DAIL k": "int"},
                           title="TEP with DAIL-SQL as B")


# Daftar sumber yang dipakai, untuk dicek peneliti
def sources_table(runs: dict) -> pd.DataFrame:
    rows = [{"Model": m, "Condition": LABELS[c], "Source": str(r.source), "Kind": r.kind,
             "Queries": len(r.logs) if r.logs is not None else None, "Few-shot k": r.k,
             "Full model name": r.meta.get("llm_model"), "Sample ratio": r.meta.get("sample_ratio"),
             "Commit": r.meta.get("commit"), "Problem": r.problem}
            for m, by_cond in runs.items() for c, r in by_cond.items()]
    return rt.with_formats(pd.DataFrame(rows), {"Queries": "int", "Few-shot k": "int"}, title="Sources")


# Simpan JSON dan Excel
def save_results(rows: list, runs: dict, notes: list, alpha: float, dail_k: int, out_dir: Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, xlsx_path = out_dir / "hasil_tep.json", out_dir / "hasil_tep.xlsx"
    # JSON: angka mentah, tanpa format
    json_path.write_text(json.dumps({
        "definition": "TEP_c = ((EX_c - EX_B) / EX_B) / ((T_c - T_B) / T_B), B = DAIL-SQL, c = 1-stage or 2-stage",
        "alpha": alpha, "dail_k": dail_k, "notes": notes, "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    # Excel: sheet TEP + sheet sumber dan catatan
    Sheet._n_tables = 0
    wb = Workbook()
    wb.remove(wb.active)
    sheet = Sheet(wb, "TEP")
    sheet.table(tep_table(rows))
    sheet.finish()
    sheet = Sheet(wb, "Sources")
    sheet.table(sources_table(runs))
    sheet.table(pd.DataFrame({"Note": notes or ["None"]}))
    sheet.finish()
    wb.save(xlsx_path)
    return json_path, xlsx_path
