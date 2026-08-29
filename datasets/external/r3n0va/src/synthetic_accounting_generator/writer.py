from __future__ import annotations

import csv
import shutil
from pathlib import Path


class DatasetWriter:
    def __init__(self, output_dir: Path, delimiter: str = ",", overwrite: bool = True) -> None:
        if output_dir.exists() and overwrite:
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = output_dir
        self.delimiter = delimiter
        self.files = {}
        self.writers = {}
        self.row_counts = {}

    def write(self, table: str, row: dict) -> None:
        if table not in self.writers:
            handle = (self.output_dir / f"{table}.csv").open("w", newline="", encoding="utf-8")
            writer = csv.DictWriter(handle, fieldnames=list(row), delimiter=self.delimiter)
            writer.writeheader()
            self.files[table] = handle
            self.writers[table] = writer
            self.row_counts[table] = 0
        self.writers[table].writerow(row)
        self.row_counts[table] += 1

    def close(self) -> None:
        for handle in self.files.values():
            handle.close()
        self.files.clear()
        self.writers.clear()
