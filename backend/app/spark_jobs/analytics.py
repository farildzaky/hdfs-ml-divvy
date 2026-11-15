"""Descriptive analytics with Spark. All numbers are computed from HDFS data."""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

DOW = {1: "Min", 2: "Sen", 3: "Sel", 4: "Rab", 5: "Kam", 6: "Jum", 7: "Sab"}


def _pivot(df: DataFrame, key: str) -> list:
    """{key, member, casual} rows from a grouped count by rider type."""
    rows = df.groupBy(key, "member_casual").count().collect()
    table: dict = {}
    for r in rows:
        table.setdefault(r[key], {key: r[key], "member": 0, "casual": 0})[r["member_casual"]] = r["count"]
    return [table[k] for k in sorted(table)]


def compute(rides: DataFrame) -> "tuple[dict, dict]":
    rides = (rides.withColumn("hour", F.hour("started_at"))
             .withColumn("dow", F.dayofweek("started_at"))
             .withColumn("weekend", F.dayofweek("started_at").isin(1, 7)))

    k = rides.agg(
        F.count("*").alias("rides"),
        F.sum((F.col("member_casual") == "member").cast("int")).alias("member_rides"),
        F.sum((F.col("rideable_type") == "electric_bike").cast("int")).alias("electric_rides"),
        F.sum((F.col("start_station_name").isNull() | F.col("end_station_name").isNull()).cast("int"))
        .alias("rides_without_station"),
        F.sum((F.col("weekend")).cast("int")).alias("weekend_rides"),
        F.avg("duration_min").alias("avg_duration"),
        F.expr("percentile_approx(duration_min, 0.5)").alias("median_duration"),
        F.min("started_at").alias("date_from"), F.max("started_at").alias("date_to"),
        F.countDistinct("start_station_name").alias("stations"),
        F.countDistinct("month").alias("months"),
    ).first().asDict()
    n = k["rides"]
    kpis = {
        "rides": n, "stations": k["stations"], "months": k["months"],
        "member_share": round(k["member_rides"] / n, 4),
        "electric_share": round(k["electric_rides"] / n, 4),
        "without_station_share": round(k["rides_without_station"] / n, 4),
        "weekend_share": round(k["weekend_rides"] / n, 4),
        "avg_duration_min": round(k["avg_duration"], 2),
        "median_duration_min": round(k["median_duration"], 2),
        "date_from": str(k["date_from"])[:10], "date_to": str(k["date_to"])[:10],
    }

    by_type = rides.groupBy("member_casual").agg(
        F.count("*").alias("rides"),
        F.avg("duration_min").alias("avg_duration"),
        F.expr("percentile_approx(duration_min, 0.5)").alias("median_duration"),
        F.avg("distance_km").alias("avg_distance"),
        F.avg(F.col("weekend").cast("int")).alias("weekend_share"),
        F.avg((F.col("start_station_name").isNotNull()
               & F.col("start_station_name").eqNullSafe(F.col("end_station_name"))).cast("int"))
        .alias("round_trip_share"),
        F.avg(((~F.col("weekend"))
               & (F.col("hour").between(7, 9) | F.col("hour").between(16, 18))).cast("int"))
        .alias("commute_peak_share"),
    ).collect()

    weekday_hourly = _pivot(rides.filter(~F.col("weekend")), "hour")
    weekend_hourly = _pivot(rides.filter(F.col("weekend")), "hour")
    by_dow = _pivot(rides, "dow")
    for r in by_dow:
        r["day"] = DOW[r["dow"]]

    top_stations = (rides.filter(F.col("start_station_name").isNotNull())
                    .groupBy("start_station_name")
                    .agg(F.count("*").alias("rides"),
                         F.avg((F.col("member_casual") == "casual").cast("int")).alias("casual_share"))
                    .orderBy(F.desc("rides")).limit(15).collect())
    top_routes = (rides.filter(F.col("start_station_name").isNotNull()
                               & F.col("end_station_name").isNotNull()
                               & (F.col("start_station_name") != F.col("end_station_name")))
                  .groupBy("start_station_name", "end_station_name").count()
                  .orderBy(F.desc("count")).limit(10).collect())

    out = {
        "monthly": _pivot(rides, "month"),
        "weekday_hourly": weekday_hourly,
        "weekend_hourly": weekend_hourly,
        "by_dow": by_dow,
        "by_bike": _pivot(rides, "rideable_type"),
        "by_rider": [{"member_casual": r["member_casual"], "rides": r["rides"],
                      "avg_duration": round(r["avg_duration"], 2),
                      "median_duration": round(r["median_duration"], 2),
                      "avg_distance": round(r["avg_distance"] or 0, 3),
                      "weekend_share": round(r["weekend_share"], 4),
                      "round_trip_share": round(r["round_trip_share"], 4),
                      "commute_peak_share": round(r["commute_peak_share"], 4)} for r in by_type],
        "top_stations": [{"station": r["start_station_name"], "rides": r["rides"],
                          "casual_share": round(r["casual_share"], 4)} for r in top_stations],
        "top_routes": [{"from": r["start_station_name"], "to": r["end_station_name"],
                        "rides": r["count"]} for r in top_routes],
    }
    return kpis, out
