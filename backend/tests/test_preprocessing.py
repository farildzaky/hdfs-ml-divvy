import pandas as pd
import pyarrow.parquet as pq
import pytest

from app import preprocessing as pp

HEADER = pp.REQUIRED


def ride(i, start="2026-09-10 08:00:00.123", end="2026-09-10 08:20:00.000",
         who="member", lat=41.88, name="Station A", sid="13022"):
    return [f"R{i}", "electric_bike", start, end, name, sid, "Station B", "13023",
            lat, -87.63, 41.89, -87.64, who]


def write_csv(path, rows):
    pd.DataFrame(rows, columns=HEADER).to_csv(path, index=False)
    return path


def steps(report):
    return {s["step"]: s["rows_removed"] for s in report["steps"]}


def read_month(out, month):
    return pq.read_table(out / f"month={month}").to_pandas()


def test_csv_values_keep_their_types(tmp_path):
    rows = [ride(1), ride(2, start="2026-09-11 09:00:00", end="2026-09-11 09:30:00")]
    report = pp.process_file(write_csv(tmp_path / "a.csv", rows), "a.csv", tmp_path / "out", 0)
    assert report["rows_output"] == 2
    df = read_month(tmp_path / "out", "2026-09").set_index("ride_id")
    assert df.loc["R2", "start_station_id"] == "13022"
    assert df.loc["R2", "duration_min"] == 30.0
    assert df.loc["R1", "started_at"] == pd.Timestamp("2026-09-10 08:00:00.123")


def test_cleaning_rules_are_counted(tmp_path):
    rows = [
        ride(1), ride(1),                                  # duplicate id
        ride(2, start="bukan tanggal"),                    # bad time
        ride(3, who="visitor"),                            # bad rider type
        ride(4, end="2026-09-10 08:00:10.000"),            # under a minute
        ride(5, end="2026-09-12 08:00:00.000"),            # over 24 hours
        ride(6, lat=""),                                   # no start coordinates
        ride(7, lat=10.0),                                 # distance glitch
        ride(8, start="2024-12-31 08:00:00", end="2024-12-31 08:20:00"),  # too old
    ]
    report = pp.process_file(write_csv(tmp_path / "a.csv", rows), "a.csv", tmp_path / "o", 0)
    s = steps(report)
    assert s["drop_duplicates"] == 1 and s["parse_time"] == 1 and s["rider_type"] == 1
    assert s["duration"] == 2 and s["start_coords"] == 1 and s["distance"] == 1 and s["too_old"] == 1
    assert report["rows_output"] == 1


def test_rides_without_station_are_kept(tmp_path):
    report = pp.process_file(write_csv(tmp_path / "a.csv", [ride(1, name="", sid="")]), "a.csv", tmp_path / "o", 0)
    assert report["rows_output"] == 1 and report["rows_without_station"] == 1
    assert read_month(tmp_path / "o", "2026-09")["start_station_name"].isna().all()


def test_spillover_joins_main_month_so_it_cannot_overwrite_neighbour(tmp_path):
    rows = [ride(i, start="2026-12-10 08:00:00", end="2026-12-10 08:30:00") for i in range(200)]
    rows.append(ride(999, start="2026-11-30 23:58:00", end="2027-12-01 00:10:00"))
    rows[-1][3] = "2026-12-01 00:10:00"
    report = pp.process_file(write_csv(tmp_path / "a.csv", rows), "a.csv", tmp_path / "o", 0)
    assert report["months"] == {"2026-12": 201}


def test_multi_month_file_is_partitioned(tmp_path):
    rows = [ride(i, start="2026-07-10 08:00:00", end="2026-07-10 08:30:00") for i in range(5)]
    rows += [ride(i + 10, start="2026-08-10 08:00:00", end="2026-08-10 08:30:00") for i in range(5)]
    report = pp.process_file(write_csv(tmp_path / "a.csv", rows), "a.csv", tmp_path / "o", 0)
    assert report["months"] == {"2026-07": 5, "2026-08": 5}


def test_validate_rejects_wrong_columns(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("invoice,total\n1,2\n")
    with pytest.raises(pp.InvalidFile, match="kolom wajib"):
        pp.validate(p, "a.csv")


def test_validate_rejects_other_formats(tmp_path):
    p = tmp_path / "a.xlsx"
    p.write_bytes(b"bukan csv")
    with pytest.raises(pp.InvalidFile, match="hanya file .csv"):
        pp.validate(p, "a.xlsx")


def test_validate_rejects_unreadable_csv(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes(b"")
    with pytest.raises(pp.InvalidFile, match="tidak bisa dibaca"):
        pp.validate(p, "a.csv")


def test_file_with_no_surviving_rows_fails_clearly(tmp_path):
    f = write_csv(tmp_path / "a.csv", [ride(1, who="visitor")])
    with pytest.raises(pp.InvalidFile, match="tidak ada baris"):
        pp.process_file(f, "a.csv", tmp_path / "o", 0)
