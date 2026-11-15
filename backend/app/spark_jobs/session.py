"""Satu-satunya tempat membuat SparkSession.

Dipakai pipeline website (spark://spark-master:7077) dan app/train_model.py
(local[*]); alamatnya diambil dari config/env SPARK_MASTER.
"""
from __future__ import annotations

from pyspark.sql import SparkSession

from app import config


def get_spark(app_name: str = "bikeshare") -> SparkSession:
    master = config.SPARK_MASTER
    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.memory", config.SPARK_DRIVER_MEMORY)
        .config("spark.sql.shuffle.partitions", "16")
        # Konversi ke pandas lewat Arrow lebih cepat, dan progress bar dimatikan supaya log bersih.
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.ui.showConsoleProgress", "false")
    )

    # Di cluster, driver berjalan di container backend; alamatnya diumumkan
    # supaya executor di worker bisa menghubunginya balik.
    if master.startswith("spark://"):
        builder = (
            builder.config("spark.executor.memory", config.SPARK_EXECUTOR_MEMORY)
            .config("spark.driver.host", "backend")
            .config("spark.driver.bindAddress", "0.0.0.0")
        )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
