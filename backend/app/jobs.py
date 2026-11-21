"""Status job disimpan di memori: API dan thread worker berbagi dictionary JOBS.

Setelah backend restart daftarnya kosong lagi; data dan hasilnya tetap ada di HDFS.
"""
from __future__ import annotations

import threading
import time

STAGES = ["queued", "preprocessing", "uploading_hdfs", "reading_hdfs", "spark_analytics",
          "loading_model", "monthly_test", "clustering", "completed", "failed"]

JOBS: "dict[str, dict]" = {}
_lock = threading.Lock()


def create(job_id: str, files: list):
    now = time.time()
    with _lock:
        JOBS[job_id] = {"id": job_id, "status": "queued", "stage": "queued", "progress": 0.0,
                        "files": files, "error": None, "timings": {}, "results_path": None,
                        "created_at": now, "updated_at": now}


def update(job_id: str, **fields):
    with _lock:
        JOBS[job_id].update(fields, updated_at=time.time())


def set_stage(job_id: str, stage: str):
    fields = {"stage": stage, "status": stage if stage in ("completed", "failed") else "running"}
    if stage in STAGES:
        fields["progress"] = round(STAGES.index(stage) / (len(STAGES) - 2), 3)
    update(job_id, **fields)


def get(job_id: str):
    with _lock:
        j = JOBS.get(job_id)
        return dict(j) if j else None


def all_jobs() -> list:
    with _lock:
        return sorted((dict(j) for j in JOBS.values()), key=lambda j: j["created_at"], reverse=True)
