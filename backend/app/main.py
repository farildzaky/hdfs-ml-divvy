"""Backend FastAPI. Alamat dasar: http://localhost:8000/api

Upload menyimpan file ke disk sedikit demi sedikit, memeriksa kolomnya, lalu memasukkan
job ke antrean yang dijalankan satu per satu oleh thread worker. API juga menyediakan
status job, hasil, daftar bulan di HDFS, dan riwayat versi model.
"""
from __future__ import annotations

import json
import queue
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config, db, pipeline, preprocessing

UPLOAD_ROOT = config.DATA_ROOT / "uploads"
RESULTS_ROOT = config.DATA_ROOT / "results"
MAX_BYTES = int(1.5 * 1024 ** 3)  # 1.5 GB/file
ALLOWED = {".csv"}

app = FastAPI(title="Bike Share Analytics API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])

_jobs_q: "queue.Queue[tuple]" = queue.Queue()


@app.on_event("startup")
def _startup():
    db.init()
    db.fail_interrupted()
    threading.Thread(target=_worker, daemon=True).start()


def _worker():
    while True:
        job_id, files = _jobs_q.get()
        try:
            pipeline.run_job(job_id, files)
        except Exception:  # noqa: BLE001  (error sudah dicatat di tabel jobs; worker tetap hidup)
            pass
        finally:
            _jobs_q.task_done()


@app.get("/api/health")
def health():
    import requests
    from app.hdfs_client import WEBHDFS
    status = {"backend": "ok"}
    try:
        r = requests.get(WEBHDFS + "/?op=LISTSTATUS", timeout=3)
        status["hdfs"] = "ok" if r.ok else f"http {r.status_code}"
    except Exception as e:  # noqa: BLE001
        status["hdfs"] = f"unreachable ({type(e).__name__})"
    status["spark_master"] = config.SPARK_MASTER
    return status


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    job_id = f"job-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    raw_dir = UPLOAD_ROOT / job_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    saved, detected = [], []
    try:
        for i, up in enumerate(files):
            display = Path(up.filename or f"file-{i}").name
            suffix = Path(display).suffix.lower()
            if suffix not in ALLOWED:
                raise HTTPException(400, f"{display}: hanya file .csv yang didukung.")
            dest = raw_dir / f"file-{i:03d}{suffix}"
            size = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = await up.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, f"{display} melebihi 1.5 GB.")
                    fh.write(chunk)
            try:
                await run_in_threadpool(preprocessing.validate, dest, display)
            except preprocessing.InvalidFile as e:
                raise HTTPException(400, str(e))
            saved.append({"path": str(dest), "name": display})
            detected.append({"name": display, "type": suffix[1:], "bytes": size})
    except HTTPException:
        shutil.rmtree(UPLOAD_ROOT / job_id, ignore_errors=True)
        raise

    db.create_job(job_id, detected)
    _jobs_q.put((job_id, saved))
    return {"job_id": job_id, "files": detected}


@app.get("/api/jobs")
def jobs():
    return db.list_jobs()


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    j = db.get_job(job_id)
    if not j:
        raise HTTPException(404, "job tidak ditemukan")
    return j


@app.get("/api/jobs/{job_id}/results")
def results(job_id: str):
    if "/" in job_id or ".." in job_id:
        raise HTTPException(404, "hasil belum tersedia")
    p = RESULTS_ROOT / job_id / "summary.json"
    if not p.exists():
        raise HTTPException(404, "hasil belum tersedia")
    return JSONResponse(json.loads(p.read_text()))


@app.get("/api/months")
def months():
    return db.list_months()


@app.get("/api/models")
def models():
    return db.list_models()
