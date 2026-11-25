"""
Tes lokal TEP dengan DAIL-SQL sebagai B (src/experiments/tep_steps.py, notebooks/eval_tep.ipynb, poin 45, 48).
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
# Default k untuk Excel tanpa akhiran _K, sama dengan notebook
DEFAULT_K = {"pipeline": 0, "dail": 9}
# Tiga perbandingan peneliti: (k GraphRAG, k DAIL)
COMPARISONS = [(0, 9), (0, 0), (9, 9)]


def _entry(i, ex, t_in, t_out, difficulty="easy"):
    return {"query_id": f"dev_{i:04d}", "db_id": "db", "difficulty": difficulty, "gold_sql": f"SELECT {i} FROM t",
            "predicted_sql": "SELECT 1", "gold_schema": ["t.a"], "predicted_schema": ["t.a"],
            "token_input": t_in, "token_output": t_out, "esm_result": ex, "ex_result": ex,
            "cm_per_clause": {c: None for c in rt.CLAUSES}}


# EX: DAIL 0.5, 1-Stage 0.5, 2-Stage 1.0. T = T_in + 3·T_out: DAIL 2030, 1-Stage 330, 2-Stage 230
DAIL = [_entry(1, 1, 2000, 10), _entry(2, 0, 2000, 10, "hard")]
ONE = [_entry(1, 1, 300, 10), _entry(2, 0, 300, 10, "hard")]
TWO = [_entry(1, 1, 200, 10), _entry(2, 1, 200, 10, "hard")]
# Run k lain: DAIL k = 0 lebih murah, GraphRAG k = 9 lebih mahal
DAIL_K0 = [_entry(1, 1, 900, 10), _entry(2, 0, 900, 10, "hard")]
ONE_K9 = [_entry(1, 1, 800, 10), _entry(2, 1, 800, 10, "hard")]
TWO_K9 = [_entry(1, 1, 700, 10), _entry(2, 0, 700, 10, "hard")]


def _expected(b_logs, c_logs):
    mean = lambda xs: sum(xs) / len(xs)
    t = lambda logs: mean([e["token_input"] + ALPHA * e["token_output"] for e in logs])
    return compute_tep(mean([e["ex_result"] for e in b_logs]), mean([e["ex_result"] for e in c_logs]),
                       t(b_logs), t(c_logs)).tep


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


def _by(rows, model, pipeline, comparison=(0, 9)):
    label = ts.comparison_label(*comparison)
    return next(r for r in rows if r["Model"] == model and r["Pipeline"] == pipeline and r["Comparison"] == label)


def test_tep_from_extracted_zips():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _pipeline_zip(root, "7B")
        _dail_zip(root, "7B")
        runs, notes = ts.find_runs([root])
        assert notes == [] and set(runs["7B"]) == {("baseline", 0), ("graphrag", 0), ("dail", 9)}
        rows = ts.tep_rows(runs, ALPHA, [(0, 9)])
    one, two = _by(rows, "7B", "1-stage"), _by(rows, "7B", "2-stage")
    assert one["Status"] == "ok" and two["Status"] == "ok"
    assert abs(two["TEP"] - _expected(DAIL, TWO)) < 1e-12 and abs(one["TEP"] - _expected(DAIL, ONE)) < 1e-12
    # 2-Stage: ((1.0 - 0.5) / 0.5) / ((230 - 2030) / 2030) = -1.1278
    assert abs(two["TEP"] - (1.0 / (-1800 / 2030))) < 1e-12
    assert one["TEP"] == 0   # EX sama dengan DAIL
    assert two["EX DAIL-SQL"] == 0.5 and two["T DAIL-SQL"] == 2030 and two["T pipeline"] == 230
    assert two["ΔEX (pp)"] == 50 and two["ΔT"] == -1800
    assert two["Few-shot k"] == 0 and two["DAIL k"] == 9 and two["Queries"] == 2
    assert two["Comparison"] == "GraphRAG K0 vs DAIL-SQL K9"


def test_three_comparisons_from_excel():
    """K0 dan K9 per kondisi: k dari akhiran nama file (huruf besar/kecil), tanpa akhiran = default."""
    with tempfile.TemporaryDirectory() as d:
        tables = Path(d)
        _excel(tables / "hasil_skripsi_7B.xlsx", [rt.per_query(ONE, TWO, ALPHA)])            # k = 0 (default)
        _excel(tables / "hasil_skripsi_7B_K9.xlsx", [rt.per_query(ONE_K9, TWO_K9, ALPHA)])
        _excel(tables / "hasil_dail_7B.xlsx", [_dail_per_query(DAIL)])                       # k = 9 (default)
        _excel(tables / "hasil_dail_7B_k0.xlsx", [_dail_per_query(DAIL_K0)])
        runs, notes = ts.find_runs([tables], DEFAULT_K)
        assert notes == [], notes
        assert set(runs["7B"]) == {("baseline", 0), ("graphrag", 0), ("baseline", 9), ("graphrag", 9),
                                   ("dail", 0), ("dail", 9)}
        assert runs["7B"][("graphrag", 9)].k_from == "nama file" and runs["7B"][("dail", 9)].k_from == "default"
        rows = ts.tep_rows(runs, ALPHA, COMPARISONS, ["7B"])
        assert ts.unused_runs(runs, COMPARISONS) == []
        # Tanpa perbandingan K0 vs K0, DAIL k = 0 tidak terpakai
        assert any("DAIL-SQL k = 0" in n for n in ts.unused_runs(runs, [(0, 9), (9, 9)]))
    assert len(rows) == 6 and all(r["Status"] == "ok" for r in rows)
    pairs = {(0, 9): (DAIL, ONE, TWO), (0, 0): (DAIL_K0, ONE, TWO), (9, 9): (DAIL, ONE_K9, TWO_K9)}
    for comp, (b, one, two) in pairs.items():
        assert abs(_by(rows, "7B", "1-stage", comp)["TEP"] - _expected(b, one)) < 1e-12, comp
        assert abs(_by(rows, "7B", "2-stage", comp)["TEP"] - _expected(b, two)) < 1e-12, comp
        assert _by(rows, "7B", "2-stage", comp)["Few-shot k"] == comp[0]
        assert _by(rows, "7B", "2-stage", comp)["DAIL k"] == comp[1]
    # K0 vs K0: pipeline lebih murah DAIL k = 0 juga, T DAIL = 930
    assert _by(rows, "7B", "1-stage", (0, 0))["T DAIL-SQL"] == 930
    assert "akhiran nama file" in _by(rows, "7B", "2-stage", (9, 9))["Note"]
    assert "EXCEL_DEFAULT_K" in _by(rows, "7B", "2-stage", (0, 9))["Note"]


def test_excel_fallback_and_zip_priority():
    with tempfile.TemporaryDirectory() as d:
        tables = Path(d) / "tables"
        filler = pd.DataFrame([{"Metric": "x", "Value": 1}])
        _excel(tables / "hasil_skripsi_7B.xlsx", [filler, rt.per_query(ONE, TWO, ALPHA)])
        _excel(tables / "hasil_dail_7B.xlsx", [_dail_per_query(DAIL)])
        # Tanpa default, k Excel tanpa akhiran tidak diketahui: dilewati dengan catatan
        runs, notes = ts.find_runs([tables])
        assert runs == {} and any("k few-shot tidak diketahui" in n for n in notes), notes
        runs, notes = ts.find_runs([tables], DEFAULT_K)
        assert all(r.kind == "excel" for r in runs["7B"].values())
        two = _by(ts.tep_rows(runs, ALPHA, [(0, 9)]), "7B", "2-stage")
        assert two["Status"] == "ok" and abs(two["TEP"] - _expected(DAIL, TWO)) < 1e-12
        assert "dari Excel" in two["Note"]

        # Zip diutamakan daripada Excel untuk model, kondisi, dan k yang sama
        models = Path(d) / "models"
        _pipeline_zip(models, "7B")
        runs, notes = ts.find_runs([models, tables], DEFAULT_K)
        assert runs["7B"][("graphrag", 0)].kind == "json" and runs["7B"][("dail", 9)].kind == "excel"
        assert any("memakai" in n for n in notes)

        # Dua Excel dengan k yang sama (tanpa akhiran = 9, dan _K9) bertabrakan: DAIL k = 9 dilewati
        _excel(tables / "hasil_dail_7B_K9.xlsx", [_dail_per_query(DAIL)])
        runs, notes = ts.find_runs([tables], DEFAULT_K)
        assert any("ditemukan 2 hasil" in n for n in notes) and ("dail", 9) not in runs["7B"], notes


def test_skips_with_reason():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _pipeline_zip(root, "7B")                          # DAIL 7B belum ada
        _pipeline_zip(root, "3B")
        _dail_zip(root, "3B", k=5)                         # DAIL k = 5 tidak diminta
        _pipeline_zip(root, "14B", one=ONE[:1], two=TWO[:1])
        _dail_zip(root, "14B")                             # pertanyaan berbeda (2 vs 1)
        runs, _ = ts.find_runs([root, root / "tidak-ada"])
        rows = ts.tep_rows(runs, ALPHA, [(0, 9), (9, 9)], ["3B", "7B", "14B", "32B"])
    assert len(rows) == 4 * 2 * 2
    assert all(r["Status"] == "skipped" and r.get("TEP") is None for r in rows)
    assert "DAIL-SQL k = 9 belum ada" in _by(rows, "3B", "2-stage")["Note"]
    assert "DAIL-SQL k = 9 belum ada" in _by(rows, "7B", "1-stage")["Note"]
    assert "pertanyaan berbeda" in _by(rows, "14B", "2-stage")["Note"]
    assert "1-stage k = 9 belum ada" in _by(rows, "14B", "1-stage", (9, 9))["Note"]
    assert "FEW_SHOT_K = 0" in _by(rows, "32B", "1-stage")["Note"]
    assert any("k = 5" in n for n in ts.unused_runs(runs, [(0, 9)]))


def test_undefined_tep_and_trial_warning():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        # 1-Stage dengan T sama persis dengan DAIL: ΔT = 0, TEP tidak terdefinisi (bukan crash)
        _pipeline_zip(root, "7B", one=DAIL, sample_ratio=0.05)
        _dail_zip(root, "7B")
        rows = ts.tep_rows(ts.find_runs([root])[0], ALPHA, [(0, 9)])
    one, two = _by(rows, "7B", "1-stage"), _by(rows, "7B", "2-stage")
    assert one["Status"] == "not_available" and "delta_t" in one["Note"]
    assert two["Status"] == "ok" and "run percobaan" in two["Note"]


def test_save_results():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _pipeline_zip(root, "7B")
        _dail_zip(root, "7B")
        runs, notes = ts.find_runs([root])
        rows = ts.tep_rows(runs, ALPHA, COMPARISONS, ["3B", "7B"])
        json_path, xlsx_path = ts.save_results(rows, runs, notes, ALPHA, COMPARISONS, root / "out")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["alpha"] == ALPHA and len(data["rows"]) == 2 * 3 * 2
        assert [c["label"] for c in data["comparisons"]] == [ts.comparison_label(*c) for c in COMPARISONS]
        wb = load_workbook(xlsx_path)
        assert wb.sheetnames == ["TEP", "Sources"]
        header = [c.value for c in wb["TEP"][1]]
        assert header == ts.COLUMNS
        wb.close()
    assert ts.model_size("Qwen/Qwen2.5-Coder-14B-Instruct") == "14B"
    assert ts.model_size("hasil_dail_7B_k5") == "7B" and ts.model_size("hasil_skripsi_7B_K9") == "7B"
    assert ts.model_size("hasil_skripsi") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"OK {name}")
