"""
Low-level storage helpers. 
ONLY modules inside api/ should import this
"""

from pathlib import Path

import os
import tempfile

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

class NotFoundError(KeyError):
    """ Raised when a record does not exist """

class DuplicateError(ValueError):
    """ Raised when creating a record whose key already exists """

class CsvTable:
    """ Generic CRUD over one CSV file, keyed by a primary-key column """

    def __init__(self, filename, key, columns):
        self.path = DATA_DIR / filename
        self.key = key
        self.columns = list(columns)

    # --- File Access ---
    def _load(self):
        if not self.path.exists():
            return pd.DataFrame(columns=self.columns)
        # keep_default_na=False: "NA" (Namibia) must stay a string, not NaN
        return pd.read_csv(self.path, keep_default_na=False, dtype=str)

    def _save(self, df):
        # write to a temp file, then swap it in, so a crash never leaves half a file
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        os.close(fd)
        try:
            df[self.columns].to_csv(tmp, index=False)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def all(self):
        return self._load()

    # ---- CREATE ---
    def create(self, record):
        df = self._load()
        record = {c: str(record.get(c, "")) for c in self.columns}
        if (df[self.key] == record[self.key]).any():
            raise DuplicateError(f"{self.key}={record[self.key]!r} already exists")
        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        self._save(df)
        return record

    # --- READ ---
    def get(self, key_value):
        df = self._load()
        match = df[df[self.key] == str(key_value)]
        if match.empty:
            raise NotFoundError(f"{self.key}={key_value!r} not found in {self.path.name}")
        return match.iloc[0].to_dict()

    def exists(self, key_value):
        df = self._load()
        return (df[self.key] == str(key_value)).any()

    # --- UPDATE ---
    def update(self, key_value, changes):
        df = self._load()
        mask = df[self.key] == str(key_value)
        if not mask.any():
            raise NotFoundError(f"{self.key}={key_value!r} not found in {self.path.name}")
        if self.key in changes and str(changes[self.key]) != str(key_value):
            raise ValueError(f"The primary key {self.key!r} cannot be changed")
        for column, value in changes.items():
            if column not in self.columns:
                raise ValueError(f"Unknown column {column!r}")
            df.loc[mask, column] = str(value)
        self._save(df)
        return df[mask].iloc[0].to_dict()

    # --- DELETE ---
    def delete(self, key_value):
        df = self._load()
        mask = df[self.key] == str(key_value)
        if not mask.any():
            raise NotFoundError(f"{self.key}={key_value!r} not found in {self.path.name}")
        self._save(df[~mask])