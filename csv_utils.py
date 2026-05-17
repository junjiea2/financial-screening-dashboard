"""Small CSV helpers for resumable data pipelines."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def append_csv_rows(
    path: str | Path,
    headers: list[str],
    rows: Iterable[dict[str, object]],
) -> None:
    file_path = Path(path)
    exists = file_path.exists() and file_path.stat().st_size > 0
    with file_path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def write_csv_rows(
    path: str | Path,
    headers: list[str],
    rows: Iterable[dict[str, object]],
) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})

