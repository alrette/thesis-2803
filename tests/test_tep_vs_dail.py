"""
Tes lokal TEP dengan DAIL-SQL sebagai B (src/experiments/tep_steps.py, notebooks/eval_tep.ipynb, poin 45).
Data sintetis: tanpa GPU, torch, atau data Spider.

    python tests/test_tep_vs_dail.py      (atau: python -m pytest tests/test_tep_vs_dail.py)
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from openpyxl import Workbook, load_workbook  # noqa: E402

from src.experiments import result_tables as rt  # noqa: E402
from src.experiments import tep_steps as ts  # noqa: E402
from src.experiments.export_excel import Sheet  # noqa: E402
from src.experiments.metrics_summary import build_metrics_results, save_metrics_results  # noqa: E402
from src.metrics.tep import compute_tep  # noqa: E402

ALPHA = 3.0


def _entry(i, ex, t_in, t_out, difficulty="easy"):
    return {"query_id": f"dev_{i:04d}", "db_id": "db", "difficulty": difficulty, "gold_sql": f"SELECT {i} FROM t",
            "predicted_sql": "SELECT 1", "gold_schema": ["t.a"], "predicted_schema": ["t.a"],
            "token_input": t_in, "token_output": t_out, "esm_result": ex, "ex_result": ex,
            "cm_per_clause": {c: None for c in rt.CLAUSES}}


# EX: DAIL 0.5, 1-Stage 0.5, 2-Stage 1.0. T = T_in + 3·T_out: DAIL 2030, 1-Stage 330, 2-Stage 230
DAIL = [_entry(1, 1, 2000, 10), _entry(2, 0, 2000, 10, "hard")]
ONE = [_entry(1, 1, 300, 10), _entry(2, 0, 300, 10, "hard")]
TWO = [_entry(1, 1, 200, 10), _entry(2, 1, 200, 10, "hard")]


def _expected(c_logs):
    mean = lambda xs: sum(xs) / len(xs)
    return compute_tep(mean([e["ex_result"] for e in DAIL]), mean([e["ex_result"] for e in c_logs]),
                       mean([e["token_input"] + ALPHA * e["token_output"] for e in DAIL]),
                       mean([e["token_input"] + ALPHA * e["token_output"] for e in c_logs])).tep


def _pipeline_zip(root: Path, size: str, one=ONE, two=TWO, k=0, sample_ratio=1.0) -> Path:
    """Isi hasil_<MODEL>.zip yang diekstrak ke outputs/models/."""
    run = root / f"Qwen2.5-Coder-{size}-Instruct"
    meta = {"llm_model": f"Qwen/Qwen2.5-Coder-{size}-Instruct", "few_shot_k": k,
            "sample_ratio": sample_ratio, "is_full_run": sample_ratio >= 1.0}
    save_metrics_results(build_metrics_results(one, two, ALPHA, meta=meta), run / "tables")
    (run / "raw_logs").mkdir(parents=True)
    (run / "raw_logs" / "baseline_log.json").write_text(json.dumps(one), encoding="utf-8")
    (run / "raw_logs" / "graphrag_log.json").write_text(json.dumps(two), encoding="utf-8")
    return run


def _dail_zip(root: Path, size: str, logs=DAIL, k=9) -> None:
    """Isi hasil_dail_<MODEL>.zip (tables/dail/, raw_logs/) yang diekstrak ke folder model."""
    run = root / f"Qwen2.5-Coder-{size}-Instruct"
    (run / "tables" / "dail").mkdir(parents=True, exist_ok=True)
    (run / "raw_logs").mkdir(parents=True, exist_ok=True)
    meta = {"llm_model": f"Qwen/Qwen2.5-Coder-{size}-Instruct", "is_full_run": True, "dail": {"dail_k_shot": k}}
    (run / "tables" / "dail" / ts.DAIL_METRICS).write_text(json.dumps({"meta": meta}), encoding="utf-8")
    (run / "raw_logs" / "dail_log.json").write_text(json.dumps(logs), encoding="utf-8")


def _excel(path: Path, tables: list) -> None:
    """Excel dengan Sheet yang sama dengan export_excel.py; sheet Per Query diawali tabel lain."""
    wb = Workbook()
    wb.remove(wb.active)
    sheet = Sheet(wb, "Per Query")
    for table in tables:
        sheet.table(table)
    sheet.finish()
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def _dail_per_query(logs) -> pd.DataFrame:
    # Kolom yang sama dengan dail_steps.per_query_table()
    return pd.DataFrame([{"Query ID": e["query_id"], "DB": e["db_id"], "Difficulty": rt.DIFF_LABEL[e["difficulty"]],
                          "Gold SQL": e["gold_sql"], "EX": e["ex_result"], "ESM": e["esm_result"],
                          "T_in": e["token_input"], "T_out": e["token_output"]} for e in logs])


def _by(rows, model, pipeline):
    return next(r for r in rows if r["Model"] == model and r["Pipeline"] == pipeline)


def test_tep_from_extracted_zips():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _pipeline_zip(root, "7B")
        _dail_zip(root, "7B")
        runs, notes = ts.find_runs([root])
        assert notes == [] and set(runs["7B"]) == {"baseline", "graphrag", "dail"}
        rows = ts.tep_rows(runs, ALPHA, 9)
    one, two = _by(rows, "7B", "1-stage"), _by(rows, "7B", "2-stage")
    assert one["Status"] == "ok" and two["Status"] == "ok"
    assert abs(two["TEP"] - _expected(TWO)) < 1e-12 and abs(one["TEP"] - _expected(ONE)) < 1e-12
    # 2-Stage: ((1.0 - 0.5) / 0.5) / ((230 - 2030) / 2030) = -1.1278
    assert abs(two["TEP"] - (1.0 / (-1800 / 2030))) < 1e-12
    assert one["TEP"] == 0   # EX sama dengan DAIL
    assert two["EX DAIL-SQL"] == 0.5 and two["T DAIL-SQL"] == 2030 and two["T pipeline"] == 230
    assert two["ΔEX (pp)"] == 50 and two["ΔT"] == -1800
    assert two["Few-shot k"] == 0 and two["DAIL k"] == 9 and two["Queries"] == 2


def test_excel_fallback_matches_zip():
    with tempfile.TemporaryDirectory() as d:
        tables = Path(d) / "tables"
        filler = pd.DataFrame([{"Metric": "x", "Value": 1}])
        _excel(tables / "hasil_skripsi_7B.xlsx", [filler, rt.per_query(ONE, TWO, ALPHA)])
        _excel(tables / "hasil_dail_7B.xlsx", [_dail_per_query(DAIL)])
        _excel(tables / "hasil_dail_7B_k5.xlsx", [_dail_per_query(DAIL)])   # ablation DAIL k = 5
        # Tanpa dail_k kedua file DAIL bertabrakan, jadi DAIL dilewati
        runs, notes = ts.find_runs([tables])
        assert any("ditemukan 2 hasil" in n for n in notes) and "dail" not in runs["7B"], notes
        # Dengan dail_k = 9, file ablation diabaikan dan file k = 9 dipakai
        runs, notes = ts.find_runs([tables], dail_k=9)
        assert any("ablation" in n for n in notes) and runs["7B"]["dail"].source.name == "hasil_dail_7B.xlsx"
        assert all(r.kind == "excel" for r in runs["7B"].values())
        rows = ts.tep_rows(runs, ALPHA, 9)
        two = _by(rows, "7B", "2-stage")
        assert two["Status"] == "ok" and abs(two["TEP"] - _expected(TWO)) < 1e-12
        assert "dari Excel" in two["Note"]

        # Zip diutamakan daripada Excel untuk model dan kondisi yang sama
        models = Path(d) / "models"
        _pipeline_zip(models, "7B")
        runs, notes = ts.find_runs([models, tables], dail_k=9)
        assert runs["7B"]["graphrag"].kind == "json" and runs["7B"]["dail"].kind == "excel"
        assert any("memakai" in n for n in notes)


def test_skips_with_reason():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _pipeline_zip(root, "7B")                          # DAIL 7B belum ada
        _pipeline_zip(root, "3B")
        _dail_zip(root, "3B", k=5)                         # DAIL ablation, bukan baseline skripsi
        _pipeline_zip(root, "14B", one=ONE[:1], two=TWO[:1])
        _dail_zip(root, "14B")                             # pertanyaan berbeda (2 vs 1)
        runs, _ = ts.find_runs([root, root / "tidak-ada"])
        rows = ts.tep_rows(runs, ALPHA, 9, ["3B", "7B", "14B", "32B"])
    assert [r["Model"] for r in rows] == ["3B", "3B", "7B", "7B", "14B", "14B", "32B", "32B"]
    assert all(r["Status"] == "skipped" and r["TEP"] is None for r in rows if "TEP" in r)
    assert "ablation" in _by(rows, "3B", "2-stage")["Note"]
    assert "DAIL-SQL belum ada" in _by(rows, "7B", "1-stage")["Note"]
    assert "pertanyaan berbeda" in _by(rows, "14B", "2-stage")["Note"]
    assert "hasil_32B.zip" in _by(rows, "32B", "1-stage")["Note"]


def test_undefined_tep_and_trial_warning():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        # 1-Stage dengan T sama persis dengan DAIL: ΔT = 0, TEP tidak terdefinisi (bukan crash)
        _pipeline_zip(root, "7B", one=DAIL, sample_ratio=0.05)
        _dail_zip(root, "7B")
        rows = ts.tep_rows(ts.find_runs([root])[0], ALPHA, 9)
    one, two = _by(rows, "7B", "1-stage"), _by(rows, "7B", "2-stage")
    assert one["Status"] == "not_available" and "delta_t" in one["Note"]
    assert two["Status"] == "ok" and "run percobaan" in two["Note"]


def test_save_results():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _pipeline_zip(root, "7B")
        _dail_zip(root, "7B")
        runs, notes = ts.find_runs([root])
        rows = ts.tep_rows(runs, ALPHA, 9, ["3B", "7B"])
        json_path, xlsx_path = ts.save_results(rows, runs, notes, ALPHA, 9, root / "out")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["alpha"] == ALPHA and len(data["rows"]) == 4
        wb = load_workbook(xlsx_path)
        assert wb.sheetnames == ["TEP", "Sources"]
        header = [c.value for c in wb["TEP"][1]]
        assert header == ts.COLUMNS
        wb.close()
    assert ts.model_size("Qwen/Qwen2.5-Coder-14B-Instruct") == "14B"
    assert ts.model_size("hasil_dail_7B_k5") == "7B" and ts.model_size("hasil_skripsi") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"OK {name}")
