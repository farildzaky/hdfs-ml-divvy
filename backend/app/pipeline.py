
from __future__ import annotations

import json
import shutil
import time
import traceback
from pathlib import Path
from typing import List

from pyspark.ml import PipelineModel
from pyspark.sql import functions as F

from app import config, hdfs_client, insights, jobs, preprocessing
from app.spark_jobs import analytics, rider_model as rm, stations
from app.spark_jobs.session import get_spark

COLUMNS = ["ride_id", "rideable_type", "started_at", "ended_at", "start_station_name",
           "end_station_name", "start_lat", "start_lng", "member_casual",
           "duration_min", "distance_km", "month"]
MODEL_HDFS = f"{config.HDFS_BASE}/models/gbt-2025"


def _round_metrics(m: dict) -> dict:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()}


def _upload_months(files: List[dict], clean_dir: Path, months: dict, hdfs_paths: dict):
    for month in months:
        target = f"{hdfs_paths['clean']}/month={month}"
        hdfs_client.delete(target)
        hdfs_client.put_tree(clean_dir / f"month={month}", target)
    hdfs_client.mkdirs(hdfs_paths["raw"])
    for f in files:
        hdfs_client.put_file(Path(f["path"]), f"{hdfs_paths['raw']}/{Path(f['path']).name}")


def _load_model():
    if not hdfs_client.exists(MODEL_HDFS):
        hdfs_client.put_tree(config.MODEL_DIR / "pipeline", MODEL_HDFS)
    return PipelineModel.load(config.HDFS_NAMENODE + MODEL_HDFS)


def _test_months(model, rides, months: List[str]) -> dict:
    return {month: rm.evaluate(model, rm.cap(rides.filter(F.col("month") == month), config.EVAL_MAX_ROWS))
            for month in months}


def _monthly_row(month: str, metrics: dict) -> dict:
    cm = metrics["confusion_matrix"]
    return {"month": month, "rows": metrics["rows"],
            "correct": cm["tp"] + cm["tn"], "wrong": cm["fp"] + cm["fn"],
            **_round_metrics({k: metrics[k] for k in ("accuracy", "baseline_accuracy", "precision",
                                                      "recall", "f1", "auc_roc", "casual_share")})}


def _score(rides, months: List[str], mark) -> dict:
    if not (config.MODEL_DIR / "info.json").exists():
        return {"available": False,
                "reason": "Model belum dilatih. Jalankan app.train_model sekali, lalu import ulang."}

    info = json.loads((config.MODEL_DIR / "info.json").read_text())
    history = json.loads((config.MODEL_DIR / "station_history.json").read_text())
    model = mark("loading_model", _load_model)
    tests = mark("monthly_test", lambda: _test_months(model, rm.add_station_history(rides, history), months))

    latest = tests[months[-1]]
    m = latest["metrics"]
    metrics = _round_metrics({k: m[k] for k in ("auc_pr", "auc_roc", "f1", "precision", "recall",
                                                "accuracy", "baseline_accuracy", "casual_share", "rows")})
    return {
        "available": True,
        "target": "casual = 1, member = 0",
        "algorithm": "gbt",
        "params": rm.GBT_PARAMS,
        "threshold": rm.THRESHOLD,
        "split": {"train": info["train_months"], "test_months": months, "test": months[-1]},
        "feature_importance": rm.feature_importance(model),
        "monthly_tests": [_monthly_row(m, tests[m]["metrics"]) for m in months],
        "model_path": config.HDFS_NAMENODE + MODEL_HDFS,
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
                  "models": MODEL_HDFS, "results": f"{base}/results/{job_id}"}
    mark("uploading_hdfs", lambda: _upload_months(files, clean_dir, report["months"], hdfs_paths))

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
        model = _score(rides, months, mark)
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
        shutil.rmtree(work, ignore_errors=True)


def run_job(job_id: str, files: List[dict], echo: bool = False) -> dict:
    def progress(stage):
        jobs.set_stage(job_id, stage)
        if echo:
            print(">>", stage, flush=True)
    try:
        summary = run(job_id, files, progress)
    except Exception as e:
        jobs.update(job_id, status="failed",
                    error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[:2000]}")
        raise
    jobs.update(job_id, status="completed", stage="completed", progress=1.0,
                timings=summary["timings"],
                results_path=str(config.DATA_ROOT / "results" / job_id / "summary.json"))
    return summary
