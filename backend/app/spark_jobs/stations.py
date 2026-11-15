"""Station clustering with KMeans: k=3, or the next k if 3 only isolates outliers."""
from __future__ import annotations

from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from app import config

FEATURES = ["log_rides", "casual_share", "weekend_share", "commute_share",
            "avg_duration", "round_trip_share", "electric_share"]


def _describe(c: dict, overall: dict) -> "tuple[str, str]":
    """Name a cluster by how it differs from the average station."""
    volume = "ramai" if c["avg_rides"] >= overall["avg_rides"] * 1.5 else (
        "sepi" if c["avg_rides"] <= overall["avg_rides"] * 0.5 else "sedang")
    if c["casual_share"] >= overall["casual_share"] + 0.08:
        return (f"Rekreasi ({volume})",
                "Banyak pengguna biasa: pasang promosi keanggotaan dan siapkan sepeda ekstra saat akhir pekan.")
    if c["commute_share"] >= overall["commute_share"] + 0.04:
        return (f"Komuter ({volume})",
                "Puncak saat jam kerja: prioritaskan pemindahan sepeda sebelum jam sibuk pagi dan sore.")
    if volume == "sepi":
        return ("Lokal (sepi)", "Pemakaian rendah: evaluasi kapasitas dok sebelum menambah sepeda.")
    return (f"Campuran ({volume})", "Pola seimbang: pantau rutin dan sesuaikan dengan musim.")


def usable_k(sizes: list, total: int) -> bool:
    """Silhouette can reward k that merely isolates a few outlier stations, which
    says nothing about groups of stations. Require every cluster to be a real group."""
    return min(sizes) >= max(10, int(total * config.MIN_CLUSTER_SHARE))


def run(spark, rides: DataFrame) -> dict:
    base = rides.filter(F.col("start_station_name").isNotNull())
    weekend = F.dayofweek("started_at").isin(1, 7)
    hour = F.hour("started_at")
    st = (base.groupBy("start_station_name").agg(
        F.count("*").alias("rides"),
        F.avg("start_lat").alias("lat"), F.avg("start_lng").alias("lng"),
        F.avg((F.col("member_casual") == "casual").cast("int")).alias("casual_share"),
        F.avg(weekend.cast("int")).alias("weekend_share"),
        F.avg(((~weekend) & (hour.between(7, 9) | hour.between(16, 18))).cast("int")).alias("commute_share"),
        F.avg(F.least(F.col("duration_min"), F.lit(120.0))).alias("avg_duration"),
        F.avg(F.col("start_station_name").eqNullSafe(F.col("end_station_name")).cast("int")).alias("round_trip_share"),
        F.avg((F.col("rideable_type") == "electric_bike").cast("int")).alias("electric_share"),
    ).filter(F.col("rides") >= config.MIN_STATION_RIDES)
          .withColumn("log_rides", F.log1p("rides")).coalesce(1).cache())

    assembled = VectorAssembler(inputCols=FEATURES, outputCol="raw").transform(st)
    scaled = (StandardScaler(inputCol="raw", outputCol="features", withMean=True)
              .fit(assembled).transform(assembled).cache())
    evaluator = ClusteringEvaluator(featuresCol="features")
    total = scaled.count()
    scores, fits = {}, []
    for k in range(3, 7):
        model = KMeans(featuresCol="features", k=k, seed=config.SEED).fit(scaled)
        s = evaluator.evaluate(model.transform(scaled))
        scores[str(k)] = round(s, 4)
        fits.append((s, k, model, usable_k(model.summary.clusterSizes, total)))
        if fits[-1][3]:
            break
    usable = [f for f in fits if f[3]] or fits
    sil, k, model, _ = max(usable, key=lambda f: f[0])
    pred = model.transform(scaled).withColumnRenamed("prediction", "cluster")

    overall = st.agg(F.avg("rides").alias("avg_rides"), F.avg("casual_share").alias("casual_share"),
                     F.avg("commute_share").alias("commute_share")).first().asDict()
    clusters = []
    for r in (pred.groupBy("cluster").agg(
            F.count("*").alias("size"), F.avg("rides").alias("avg_rides"),
            F.avg("casual_share").alias("casual_share"), F.avg("weekend_share").alias("weekend_share"),
            F.avg("commute_share").alias("commute_share"), F.avg("avg_duration").alias("avg_duration"),
            F.avg("round_trip_share").alias("round_trip_share"),
            F.avg("electric_share").alias("electric_share")).orderBy("cluster").collect()):
        c = r.asDict()
        c["label"], c["recommendation"] = _describe(c, overall)
        clusters.append({key: (round(v, 4) if isinstance(v, float) else v) for key, v in c.items()})
    # Two clusters can earn the same name; number them, busiest first, to tell them apart.
    for label in {c["label"] for c in clusters}:
        same = sorted((c for c in clusters if c["label"] == label), key=lambda c: -c["avg_rides"])
        if len(same) > 1:
            for i, c in enumerate(same, 1):
                c["label"] = f"{label} {i}"

    points = [{"station": r["start_station_name"], "lat": round(r["lat"], 5), "lng": round(r["lng"], 5),
               "rides": r["rides"], "cluster": r["cluster"],
               "casual_share": round(r["casual_share"], 3)}
              for r in pred.orderBy(F.desc("rides")).limit(1500).collect()]
    scaled.unpersist()
    st.unpersist()
    return {"chosen_k": k, "silhouette": round(sil, 4), "silhouette_by_k": scores,
            "min_station_rides": config.MIN_STATION_RIDES, "stations_clustered": sum(c["size"] for c in clusters),
            "clusters": clusters, "points": points}
