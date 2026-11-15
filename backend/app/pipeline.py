"""Pipeline incremental, dibaca dari atas ke bawah di run().

pembersihan -> HDFS (satu folder per bulan, import ulang mengganti) -> Spark membaca
SEMUA bulan dari HDFS -> analitik -> muat model yang sudah jadi -> uji tiap bulan ->
clustering stasiun -> summary.json. Model tidak dilatih di sini, tetapi sekali saja
di app/train_model.py.
"""
from __future__ import annotations

import json
import shutil
import time
import traceback
from pathlib import Path
from typing import List

from pyspark.ml import PipelineModel
from pyspark.sql import functions as F

from app import config, db, hdfs_client, insights, preprocessing
from app.spark_jobs import analytics, rider_model as rm, stations
from app.spark_jobs.session import get_spark

COLUMNS = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name",
           "end_station_name", "start_lat", "start_lng", "member_casual",
           "duration_min", "distance_km", "month"]


def _round_metrics(m: dict) -> dict:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()}


def _upload_months(files: List[dict], clean_dir: Path, months: dict, hdfs_paths: dict):
    """Bulan yang diimport ulang dihapus dulu, jadi datanya diganti, bukan ditambah."""
    for month in months:
        target = f"{hdfs_paths['clean']}/month={month}"
        hdfs_client.delete(target)
        hdfs_client.put_tree(clean_dir / f"month={month}", target)
    hdfs_client.mkdirs(hdfs_paths["raw"])
    for f in files:
        hdfs_client.put_file(Path(f["path"]), f"{hdfs_paths['raw']}/{Path(f['path']).name}")


def _current_model(job_id: str) -> dict:
    """Model dilatih sekali di luar website, jadi import pertama menerbitkannya ke HDFS sebagai versi 1."""
    current = db.latest_model()
    if current:
        return current
    info = json.loads((config.MODEL_DIR / "info.json").read_text())
    hdfs_dir = f"{config.HDFS_BASE}/models/v0001"
    hdfs_client.put_tree(config.MODEL_DIR / "pipeline", hdfs_dir)
    db.add_model(1, f"{config.HDFS_NAMENODE}{hdfs_dir}", "gbt", rm.THRESHOLD,
                 info["train_months"], {}, job_id)
    return db.latest_model()


def _known_tests(current: dict, new_months: List[str]) -> dict:
    """Hasil uji bulan yang tidak disentuh import ini, diambil dari job sebelumnya supaya tidak dihitung ulang."""
    p = config.DATA_ROOT / "results" / current["job_id"] / "summary.json"
    if not p.exists():
        return {}
    rows = (json.loads(p.read_text()).get("model") or {}).get("monthly_tests", [])
    return {r["month"]: r for r in rows if r["month"] not in new_months}


def _test_months(model, rides, months: List[str]) -> dict:
    return {month: rm.evaluate(model, rm.cap(rides.filter(F.col("month") == month), config.EVAL_MAX_ROWS))
            for month in months}


def _monthly_row(month: str, metrics: dict) -> dict:
    cm = metrics["confusion_matrix"]
    return {"month": month, "rows": metrics["rows"],
            "correct": cm["tp"] + cm["tn"], "wrong": cm["fp"] + cm["fn"],
            **_round_metrics({k: metrics[k] for k in ("accuracy", "baseline_accuracy", "precision",
                                                      "recall", "f1", "auc_roc", "casual_share")})}


def _score(rides, months: List[str], new_months: List[str], job_id: str, mark) -> dict:
    if not (config.MODEL_DIR / "info.json").exists():
        return {"available": False,
                "reason": "Model belum dilatih. Jalankan app.train_model sekali, lalu import ulang."}

    def _load():
        current = _current_model(job_id)
        history = json.loads((config.MODEL_DIR / "station_history.json").read_text())
        return current, PipelineModel.load(current["path"]), history
    current, model, history = mark("loading_model", _load)
    known = _known_tests(current, new_months)
    # Bulan terbaru selalu diuji, karena kurva dan confusion matrix-nya tidak disimpan per bulan.
    to_test = [m for m in months if m not in known or m == months[-1]]
    tests = mark("monthly_test", lambda: _test_months(model, rm.add_station_history(rides, history), to_test))

    latest = tests[months[-1]]
    m = latest["metrics"]
    metrics = _round_metrics({k: m[k] for k in ("auc_pr", "auc_roc", "f1", "precision", "recall",
                                                "accuracy", "baseline_accuracy", "casual_share", "rows")})
    db.update_model_result(current["version"], metrics, job_id)
    return {
        "available": True,
        "target": "casual = 1, member = 0",
        "algorithm": "gbt",
        "params": rm.GBT_PARAMS,
        "threshold": rm.THRESHOLD,
        "split": {"train": current["train_months"], "test_months": months, "test": months[-1]},
        "feature_importance": rm.feature_importance(model),
        "monthly_tests": [_monthly_row(m, tests[m]["metrics"]) if m in tests else known[m] for m in months],
        "model_version": current["version"],
        "model_path": current["path"],
        "test_metrics": metrics,
        "confusion_matrix": m["confusion_matrix"],
        "roc_curve": latest["roc_curve"], "pr_curve": latest["pr_curve"],
    }


def run(job_id: str, files: List[dict], progress) -> dict:
    timings = {}

    def mark(stage, fn):
        progress(stage)
        s = time.time()
        out = fn()
        timings[stage] = round(time.time() - s, 1)
        return out

    work = config.DATA_ROOT / "uploads" / job_id
    clean_dir = work / "clean"
    report = mark("preprocessing", lambda: preprocessing.run_all(files, clean_dir))

    base = config.HDFS_BASE
    hdfs_paths = {"raw": f"{base}/raw/{job_id}", "clean": f"{base}/clean",
                  "models": f"{base}/models", "results": f"{base}/results/{job_id}"}
    mark("uploading_hdfs", lambda: _upload_months(files, clean_dir, report["months"], hdfs_paths))
    for month, rows in report["months"].items():
        db.upsert_month(month, rows, job_id)

    spark = get_spark(f"pipeline-{job_id}")
    try:
        def _read():
            loaded = spark.read.parquet(config.HDFS_NAMENODE + hdfs_paths["clean"]).select(*COLUMNS)
            rides = rm.add_features(loaded.dropDuplicates(["ride_id"])).cache()
            return rides, loaded.count(), rides.count()
        rides, total, distinct = mark("reading_hdfs", _read)
        report["cross_file_duplicates_removed"] = total - distinct
        months = sorted(r["month"] for r in rides.select("month").distinct().collect())

        kpis, analytics_out = mark("spark_analytics", lambda: analytics.compute(rides))
        model = _score(rides, months, list(report["months"]), job_id, mark)
        clusters = mark("clustering", lambda: stations.run(spark, rides))

        summary = {
            "job_id": job_id,
            "months_in_store": months,
            "months_imported": list(report["months"]),
            "preprocessing_report": {**report, "hdfs_paths": hdfs_paths},
            "kpis": kpis,
            "analytics": analytics_out,
            "model": model,
            "stations": clusters,
            "insights": insights.build(kpis, analytics_out, model, clusters),
            "timings": timings,
            "hdfs_results_path": hdfs_paths["results"],
        }
        out_dir = config.DATA_ROOT / "results" / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
        hdfs_client.mkdirs(hdfs_paths["results"])
        hdfs_client.put_file(out_dir / "summary.json", f"{hdfs_paths['results']}/summary.json")
        progress("completed")
        return summary
    finally:
        spark.stop()
        # Salinan mentah dan bersih sudah ada di HDFS, jadi file upload lokal boleh dihapus.
        shutil.rmtree(work, ignore_errors=True)


def run_job(job_id: str, files: List[dict], echo: bool = False) -> dict:
    """Dipakai website dan CLI: jalankan pipeline sambil mencatat tahap dan hasilnya di tabel jobs."""
    def progress(stage):
        db.set_stage(job_id, stage)
        if echo:
            print(">>", stage, flush=True)
    try:
        summary = run(job_id, files, progress)
    except Exception as e:
        db.update_job(job_id, status="failed",
                      error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[:2000]}")
        raise
    db.update_job(job_id, status="completed", stage="completed", progress=1.0,
                  timings_json=json.dumps(summary["timings"]),
                  results_path=str(config.DATA_ROOT / "results" / job_id / "summary.json"))
    return summary
