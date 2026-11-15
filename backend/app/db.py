"""Metadata di SQLite: job pipeline, bulan yang sudah diimport, dan versi model.

Sengaja kecil dan tanpa library tambahan supaya API dan thread worker bisa berbagi
status. Datanya sendiri disimpan di HDFS.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(os.getenv("JOBS_DB", "/opt/app/data/jobs.sqlite"))
_lock = threading.Lock()

STAGES = ["queued", "preprocessing", "uploading_hdfs", "reading_hdfs", "spark_analytics",
          "loading_model", "monthly_test", "clustering", "completed", "failed"]


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, stage TEXT,
                progress REAL DEFAULT 0, files_json TEXT, error TEXT,
                timings_json TEXT, results_path TEXT,
                created_at REAL, updated_at REAL)""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS months (
                month TEXT PRIMARY KEY, rows INTEGER, job_id TEXT, imported_at REAL)""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS models (
                version INTEGER PRIMARY KEY, path TEXT, algorithm TEXT, threshold REAL,
                train_months_json TEXT, metrics_json TEXT, job_id TEXT, created_at REAL)""")


def fail_interrupted():
    """Worker berjalan di proses ini, jadi saat backend baru menyala tidak mungkin ada job yang masih berjalan."""
    with _lock, _conn() as c:
        c.execute("UPDATE jobs SET status='failed', error=?, updated_at=?"
                  " WHERE status IN ('queued','running')",
                  ("Job terhenti karena backend mati atau restart. Silakan import ulang.", time.time()))


def create_job(job_id: str, files: list):
    now = time.time()
    with _lock, _conn() as c:
        c.execute("INSERT INTO jobs (id,status,stage,progress,files_json,created_at,updated_at)"
                  " VALUES (?,?,?,?,?,?,?)",
                  (job_id, "queued", "queued", 0.0, json.dumps(files), now, now))


def update_job(job_id: str, **fields):
    if not fields:
        return
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))


def set_stage(job_id: str, stage: str):
    try:
        progress = round(STAGES.index(stage) / (len(STAGES) - 2), 3)
    except ValueError:
        progress = None
    update_job(job_id, stage=stage, status=stage if stage in ("completed", "failed") else "running",
               **({"progress": progress} if progress is not None else {}))


def get_job(job_id: str):
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _row(r) if r else None


def list_jobs() -> list:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [_row(r) for r in rows]


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["files"] = json.loads(d.pop("files_json") or "[]")
    d["timings"] = json.loads(d.pop("timings_json") or "{}")
    return d


def upsert_month(month: str, rows: int, job_id: str):
    with _lock, _conn() as c:
        c.execute("INSERT OR REPLACE INTO months (month,rows,job_id,imported_at) VALUES (?,?,?,?)",
                  (month, rows, job_id, time.time()))


def list_months() -> list:
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM months ORDER BY month")]


def add_model(version: int, path: str, algorithm: str, threshold: float,
              train_months: list, metrics: dict, job_id: str):
    with _lock, _conn() as c:
        c.execute("INSERT INTO models VALUES (?,?,?,?,?,?,?,?)",
                  (version, path, algorithm, threshold, json.dumps(train_months),
                   json.dumps(metrics), job_id, time.time()))


def update_model_result(version: int, metrics: dict, job_id: str):
    """Model yang sama diuji ulang di setiap import; simpan hasil terbarunya."""
    with _lock, _conn() as c:
        c.execute("UPDATE models SET metrics_json=?, job_id=? WHERE version=?",
                  (json.dumps(metrics), job_id, version))


def list_models() -> list:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM models ORDER BY version DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["train_months"] = json.loads(d.pop("train_months_json"))
        d["metrics"] = json.loads(d.pop("metrics_json"))
        out.append(d)
    return out


def latest_model():
    models = list_models()
    return models[0] if models else None
