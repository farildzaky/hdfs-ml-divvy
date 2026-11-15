"""Central configuration: paths, Spark/HDFS addresses, data rules, ML limits.

Everything is overridable via environment variables so the same code runs
locally and inside the Docker cluster.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = Path(os.getenv("DATA_RAW", REPO_ROOT / "data" / "raw"))
DATA_ROOT = DATA_RAW.parent

SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
HDFS_NAMENODE = os.getenv("HDFS_NAMENODE", "hdfs://namenode:9000")
SPARK_DRIVER_MEMORY = os.getenv("SPARK_DRIVER_MEMORY", "4g")
SPARK_EXECUTOR_MEMORY = os.getenv("SPARK_EXECUTOR_MEMORY", "4g")
HDFS_BASE = os.getenv("HDFS_BASE", "/bikeshare")

SEED = 42

# Trips before this date are dropped and logged, so uploads hold only actual 2026 data.
# Training overrides it (see app/train_model.py).
DATA_MIN_DATE = os.getenv("DATA_MIN_DATE", "2026-01-01")
MIN_DURATION_MIN = 1.0   # shorter rides are usually false starts / re-docks
MAX_DURATION_MIN = 24 * 60.0
MAX_DISTANCE_KM = 100.0  # beyond the service area: GPS glitch

# A month holding under this share of a file's rows is spill-over from a
# neighbouring month (a ride crossing midnight), not a month of its own.
SPILL_SHARE = 0.01

# Spark standalone here has 4 cores / 4 GB, so ML runs on bounded samples.
TRAIN_MAX_ROWS = int(os.getenv("TRAIN_MAX_ROWS", "2000000"))
EVAL_MAX_ROWS = int(os.getenv("EVAL_MAX_ROWS", "300000"))

# The finished model, written once by app/train_model.py. It survives a data reset.
MODEL_DIR = Path(os.getenv("MODEL_DIR", DATA_ROOT.parent / "model" / "gbt-2025"))

MIN_STATION_RIDES = 200
MIN_CLUSTER_SHARE = 0.03
