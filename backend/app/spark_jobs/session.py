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
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.ui.showConsoleProgress", "false")
    )


    if master.startswith("spark://"):
        builder = (
            builder.config("spark.executor.memory", config.SPARK_EXECUTOR_MEMORY)
            .config("spark.driver.host", "backend")
            .config("spark.driver.bindAddress", "0.0.0.0")
        )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
