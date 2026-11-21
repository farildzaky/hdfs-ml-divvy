import os
from pathlib import Path

import requests

WEBHDFS = os.getenv("WEBHDFS_URL", "http://namenode:9870/webhdfs/v1")
USER = os.getenv("HDFS_USER", "root")


def _call(method: str, path: str, op: str, **params) -> requests.Response:
    r = requests.request(method, WEBHDFS + path,
                         params={"op": op, "user.name": USER, **params},
                         allow_redirects=False, timeout=60)
    r.raise_for_status()
    return r


def mkdirs(path: str) -> None:
    _call("PUT", path, "MKDIRS")


def delete(path: str) -> None:
    _call("DELETE", path, "DELETE", recursive="true")


def put_file(local: Path, hdfs_path: str) -> None:
    datanode_url = _call("PUT", hdfs_path, "CREATE", overwrite="true").headers["Location"]
    with open(local, "rb") as f:
        requests.put(datanode_url, data=f, timeout=600).raise_for_status()


def put_tree(local_dir: Path, hdfs_dir: str) -> None:
    mkdirs(hdfs_dir)
    for p in local_dir.rglob("*"):
        if p.is_file() and p.suffix != ".crc":  
            put_file(p, f"{hdfs_dir}/{p.relative_to(local_dir).as_posix()}")


def list_dir(path: str) -> list:
    """Nama isi folder di HDFS; folder yang belum ada dianggap kosong."""
    try:
        r = _call("GET", path, "LISTSTATUS")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return []
        raise
    return [s["pathSuffix"] for s in r.json()["FileStatuses"]["FileStatus"]]


def exists(path: str) -> bool:
    try:
        _call("GET", path, "GETFILESTATUS")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return False
        raise
    return True
