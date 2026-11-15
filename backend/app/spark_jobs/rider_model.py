"""Rider-type classifier: from how a ride looks, was it a member or a casual?

The split is by month, never random: the model learns from 2025 once, then every
uploaded month tests it on rides it has never seen.
"""
from __future__ import annotations

import numpy as np
from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.classification import GBTClassifier
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from app import config

NUMERIC = ["hour", "day_of_week", "month_num", "is_weekend", "is_commute_peak", "duration_min",
           "distance_km", "speed_kmh", "is_round_trip", "start_lat", "start_lng",
           "has_start_station", "has_end_station"]
HISTORY = ["start_casual_history", "end_casual_history"]
CATEGORICAL = ["rideable_type"]

GBT_PARAMS = {"maxIter": 100, "maxDepth": 7, "maxBins": 64}
THRESHOLD = 0.5  # probability of casual at or above this means "casual"


def add_features(rides: DataFrame) -> DataFrame:
    dow = F.dayofweek("started_at")  # 1 = Sunday
    hour = F.hour("started_at")
    weekend = dow.isin(1, 7)
    distance = F.coalesce(F.nanvl("distance_km", F.lit(None).cast("double")), F.lit(0.0))
    return (rides
            .withColumn("label", (F.col("member_casual") == "casual").cast("int"))
            .withColumn("hour", hour.cast("double"))
            .withColumn("day_of_week", dow.cast("double"))
            .withColumn("month_num", F.month("started_at").cast("double"))
            .withColumn("is_weekend", weekend.cast("double"))
            .withColumn("is_commute_peak",
                        ((~weekend) & (hour.between(7, 9) | hour.between(16, 18))).cast("double"))
            .withColumn("distance_km", distance)
            .withColumn("speed_kmh", F.least(distance / (F.col("duration_min") / 60.0), F.lit(40.0)))
            .withColumn("is_round_trip",
                        (F.col("start_station_name").isNotNull()
                         & F.col("start_station_name").eqNullSafe(F.col("end_station_name"))).cast("double"))
            .withColumn("has_start_station", F.col("start_station_name").isNotNull().cast("double"))
            .withColumn("has_end_station", F.col("end_station_name").isNotNull().cast("double")))


def station_history(rides: DataFrame, prior: float = 100.0) -> dict:
    """Casual share of each start and end station, pulled toward the overall share
    when a station has few rides. Computed from training rides only."""
    overall = rides.agg(F.avg("label")).first()[0]
    history = {"overall": overall}
    for side in ("start", "end"):
        col = f"{side}_station_name"
        rows = (rides.filter(F.col(col).isNotNull()).groupBy(col)
                .agg(F.count("*").alias("n"), F.sum("label").alias("casual")).collect())
        history[side] = {r[col]: (r["casual"] + prior * overall) / (r["n"] + prior) for r in rows}
    return history


def add_station_history(rides: DataFrame, history: dict) -> DataFrame:
    """Stations the history has never seen, and rides without a station, get the overall share."""
    for side in ("start", "end"):
        col, value = f"{side}_station_name", f"{side}_casual_history"
        table = rides.sparkSession.createDataFrame(list(history[side].items()), f"{col} string, {value} double")
        rides = (rides.join(F.broadcast(table), col, "left")
                 .withColumn(value, F.coalesce(F.col(value), F.lit(history["overall"]))))
    return rides


def build_pipeline() -> Pipeline:
    stages = []
    for c in CATEGORICAL:
        stages.append(StringIndexer(inputCol=c, outputCol=f"{c}_idx", handleInvalid="keep"))
        stages.append(OneHotEncoder(inputCol=f"{c}_idx", outputCol=f"{c}_ohe"))
    cols = NUMERIC + HISTORY + [f"{c}_ohe" for c in CATEGORICAL]
    stages.append(VectorAssembler(inputCols=cols, outputCol="features"))
    stages.append(GBTClassifier(featuresCol="features", labelCol="label", seed=config.SEED, **GBT_PARAMS))
    return Pipeline(stages=stages)


def cap(df: DataFrame, max_rows: int) -> DataFrame:
    n = df.count()
    return df if n <= max_rows else df.sample(False, max_rows / n, seed=config.SEED)


def score(model: PipelineModel, df: DataFrame):
    pdf = (model.transform(df)
           .select(vector_to_array("probability")[1].alias("p"), "label").toPandas())
    return pdf["p"].to_numpy(), pdf["label"].to_numpy()


def metrics_at(prob, y) -> dict:
    pred = (prob >= THRESHOLD).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / len(y) if len(y) else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "accuracy": acc,
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}}


def auc_curves(prob, y):
    order = np.argsort(-prob, kind="mergesort")
    y = y[order]
    tp, fp = np.cumsum(y == 1), np.cumsum(y == 0)
    P, N = (y == 1).sum(), (y == 0).sum()
    recall = tp / P if P else np.zeros(len(y))
    precision = tp / (tp + fp)
    fpr = fp / N if N else np.zeros(len(y))
    auc_roc = float(np.trapz(np.r_[0, recall], np.r_[0, fpr]))
    auc_pr = float(np.trapz(np.r_[precision[0], precision], np.r_[0, recall]))
    idx = np.linspace(0, len(y) - 1, min(100, len(y))).astype(int)
    roc = [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(recall[i]), 4)} for i in idx]
    pr = [{"recall": round(float(recall[i]), 4), "precision": round(float(precision[i]), 4)}
          for i in idx]
    return auc_pr, auc_roc, roc, pr


def evaluate(model: PipelineModel, df: DataFrame) -> dict:
    prob, y = score(model, df)
    auc_pr, auc_roc, roc, pr = auc_curves(prob, y)
    m = metrics_at(prob, y)
    m.update({"auc_pr": auc_pr, "auc_roc": auc_roc, "rows": int(len(y)),
              "casual_share": float(y.mean()) if len(y) else 0.0,
              "baseline_accuracy": float(max(y.mean(), 1 - y.mean())) if len(y) else 0.0})
    return {"metrics": m, "roc_curve": roc, "pr_curve": pr}


def feature_importance(model: PipelineModel) -> list:
    """Name each slot of the assembled vector, expanding one-hot columns."""
    names = NUMERIC + HISTORY
    indexers = [s for s in model.stages if s.__class__.__name__ == "StringIndexerModel"]
    for ix in indexers:
        names += [f"{ix.getInputCol()}={label}" for label in ix.labels]
    vals = model.stages[-1].featureImportances.toArray()
    pairs = sorted(zip(names, vals), key=lambda x: -x[1])
    return [{"feature": n, "importance": round(float(v), 5)} for n, v in pairs]


def fit(df: DataFrame, max_rows: int) -> PipelineModel:
    train = cap(df, max_rows).cache()
    model = build_pipeline().fit(train)
    train.unpersist()
    return model
