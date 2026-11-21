from datetime import datetime

import pytest
from pyspark.sql import SparkSession

from app.spark_jobs import rider_model as rm


@pytest.fixture(scope="module")
def spark():
    s = SparkSession.builder.master("local[1]").appName("test").getOrCreate()
    yield s
    s.stop()


COLS = ["member_casual", "rideable_type", "started_at", "start_station_name", "end_station_name",
        "start_lat", "start_lng", "duration_min", "distance_km"]


def rides(spark, rows):
    return spark.createDataFrame(rows, schema=(
        "member_casual string, rideable_type string, started_at timestamp, start_station_name string,"
        " end_station_name string, start_lat double, start_lng double, duration_min double, distance_km double"))


def test_missing_stations_and_distance_give_no_null_features(spark):
    t = datetime(2026, 9, 7, 8, 0)  # a Monday
    df = rm.add_features(rides(spark, [
        ("member", "classic_bike", t, "A", None, 41.8, -87.6, 10.0, None),
        ("casual", "electric_bike", t, None, "B", 41.8, -87.6, 20.0, float("nan")),
        ("casual", "electric_bike", t, None, None, 41.8, -87.6, 20.0, 1.0),
        ("member", "classic_bike", t, "A", "A", 41.8, -87.6, 15.0, 0.0),
    ]))
    rows = df.select(*rm.NUMERIC).collect()
    assert all(v is not None and v == v for r in rows for v in r)
    assert [r["is_round_trip"] for r in rows] == [0.0, 0.0, 0.0, 1.0]
    assert rows[0]["is_commute_peak"] == 1.0 and rows[0]["is_weekend"] == 0.0


def test_pipeline_fits_on_rows_with_missing_stations(spark, monkeypatch):
    monkeypatch.setattr(rm, "GBT_PARAMS", {"maxIter": 2, "maxDepth": 2})
    t = datetime(2026, 9, 12, 14, 0)
    data = [("casual", "electric_bike", t, "A", None, 41.8, -87.6, 30.0, None)] * 5
    data += [("member", "classic_bike", datetime(2026, 9, 7, 8, 0), "A", "B", 41.9, -87.7, 8.0, 1.5)] * 5
    df = rm.add_features(rides(spark, data))
    model = rm.build_pipeline().fit(rm.add_station_history(df, rm.station_history(df)))
    names = [f["feature"] for f in rm.feature_importance(model)]
    assert any(n.startswith("rideable_type=") for n in names)
    assert "start_casual_history" in names


def test_station_history_shrinks_small_stations_and_handles_unknown_ones(spark):
    t = datetime(2025, 7, 5, 14, 0)
    train = rm.add_features(rides(spark, [("casual", "classic_bike", t, "A", "B", 41.8, -87.6, 20.0, 1.0)] * 3
                                  + [("member", "classic_bike", t, "C", "B", 41.8, -87.6, 20.0, 1.0)] * 3))
    history = rm.station_history(train, prior=3.0)
    assert history["overall"] == 0.5
    assert history["start"]["A"] == (3 + 3 * 0.5) / (3 + 3)   # all casual, pulled toward 0.5
    new = rm.add_features(rides(spark, [("member", "classic_bike", t, "Z", None, 41.8, -87.6, 20.0, 1.0)]))
    row = rm.add_station_history(new, history).first()
    assert row["start_casual_history"] == 0.5 and row["end_casual_history"] == 0.5


def test_speed_is_capped_against_gps_glitches(spark):
    t = datetime(2025, 7, 5, 14, 0)
    df = rm.add_features(rides(spark, [("member", "classic_bike", t, "A", "B", 41.8, -87.6, 6.0, 1.5),
                                       ("member", "classic_bike", t, "A", "B", 41.8, -87.6, 1.0, 50.0)]))
    assert [r["speed_kmh"] for r in df.select("speed_kmh").collect()] == [15.0, 40.0]


def test_job_progress_follows_stage_order():
    from app import jobs
    jobs.create("job-t", [])
    jobs.set_stage("job-t", "preprocessing")
    assert jobs.get("job-t")["status"] == "running" and jobs.get("job-t")["progress"] == 0.125
    jobs.set_stage("job-t", "completed")
    assert jobs.get("job-t")["status"] == "completed" and jobs.get("job-t")["progress"] == 1.0


def test_clustering_rejects_k_that_only_isolates_outliers():
    from app.spark_jobs.stations import usable_k
    assert not usable_k([607, 312, 1], 920)
    assert not usable_k([500, 400, 12], 912)   # 12 passes the floor, not 3% of stations
    assert usable_k([400, 300, 220], 920)
