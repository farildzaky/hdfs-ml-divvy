"""Menjalankan pipeline tanpa website, misalnya untuk import satu folder sekaligus:

    docker compose exec backend python -m app.cli data/raw/csv
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

from app import jobs, pipeline


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path, help="folder berisi file .csv, atau satu file")
    args = ap.parse_args()

    paths = [args.path] if args.path.is_file() else sorted(
        p for p in args.path.iterdir() if p.suffix.lower() == ".csv")
    if not paths:
        print("ERROR: tidak ada file .csv.", file=sys.stderr)
        sys.exit(2)

    job_id = f"job-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    files = [{"path": str(p), "name": p.name} for p in paths]
    jobs.create(job_id, [{"name": p.name, "type": p.suffix[1:], "bytes": p.stat().st_size} for p in paths])
    summary = pipeline.run_job(job_id, files, echo=True)
    print(json.dumps({"job_id": job_id, "kpis": summary["kpis"],
                      "test_metrics": summary["model"].get("test_metrics"),
                      "timings": summary["timings"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
