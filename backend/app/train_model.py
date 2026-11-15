"""Train the rider-type model once, outside the website, from data/raw/training:

    docker compose exec -e DATA_MIN_DATE=2025-01-01 -e SPARK_MASTER='local[*]' \\
        -e SPARK_DRIVER_MEMORY=4g backend python -m app.train_model

Training data stays out of HDFS and the job history. The result goes to model/,
and the first upload on the website publishes it to HDFS as version 1.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from app import config, preprocessing
from app.pipeline import COLUMNS
from app.spark_jobs import rider_model as rm
from app.spark_jobs.session import get_spark


def main():
    paths = sorted((config.DATA_RAW / "training").glob("*.csv"))
    if not paths:
        print("ERROR: tidak ada file .csv di data/raw/training.", file=sys.stderr)
        sys.exit(2)

    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean"
        report = preprocessing.run_all([{"path": p, "name": p.name} for p in paths], clean)
        spark = get_spark("train-model")
        spark.sparkContext.setCheckpointDir(f"{tmp}/checkpoints")  # keeps 100 rounds of boosting shallow
        try:
            rides = rm.add_features(spark.read.parquet(str(clean)).select(*COLUMNS))
            months = sorted(report["months"])
            history = rm.station_history(rides)
            model = rm.fit(rm.add_station_history(rides, history), config.TRAIN_MAX_ROWS)
            shutil.rmtree(config.MODEL_DIR, ignore_errors=True)
            config.MODEL_DIR.mkdir(parents=True)
            model.write().save(f"file://{config.MODEL_DIR / 'pipeline'}")
        finally:
            spark.stop()

    info = {"algorithm": "gbt", "params": rm.GBT_PARAMS, "train_months": months,
            "rows_cleaned": report["rows_output"], "max_rows_sampled": config.TRAIN_MAX_ROWS}
    (config.MODEL_DIR / "station_history.json").write_text(json.dumps(history))
    (config.MODEL_DIR / "info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
