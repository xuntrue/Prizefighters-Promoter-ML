"""
Arenas.py

CRUD + validation for arenas stored in data/arenas.csv.

Columns:
    ArenaID  -> int, auto-assigned (sequential, starting at 1), primary key
    Name     -> str
    Country  -> str, A-2 code, foreign key -> countries.csv

No dedicated "add arena" screen was requested for this batch of files --
arenas get added from the Arenas section in ui/settings.py (same slot
Weight Classes lives in), since this is config/reference data rather
than something recorded during play.
"""

import csv
import os

from api.Country import Country

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
ARENAS_FILE = os.path.join(DATA_DIR, "arenas.csv")

FIELDNAMES = ["ArenaID", "Name", "Country"]


class ArenaError(Exception):
    """Raised when an arena entry fails validation."""
    pass


class Arenas:
    """CRUD for arenas stored in arenas.csv."""

    def __init__(self, filepath: str = ARENAS_FILE, country_api: Country = None):
        self.filepath = filepath
        self.country_api = country_api or Country()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()

    def get_all(self) -> list:
        self._ensure_file_exists()
        with open(self.filepath, newline="", encoding="utf-8") as f:
            rows = [
                {
                    "arena_id": int(row["ArenaID"]),
                    "name": row["Name"],
                    "country": row["Country"],
                }
                for row in csv.DictReader(f)
            ]
        return sorted(rows, key=lambda r: r["name"].lower())

    def get_by_id(self, arena_id: int):
        for row in self.get_all():
            if row["arena_id"] == arena_id:
                return row
        return None

    def exists(self, arena_id: int) -> bool:
        return self.get_by_id(arena_id) is not None

    def _save_all(self, rows: list):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["arena_id"]):
                writer.writerow({"ArenaID": row["arena_id"], "Name": row["name"], "Country": row["country"]})

    def _next_id(self) -> int:
        existing = self.get_all()
        if not existing:
            return 1
        return max(row["arena_id"] for row in existing) + 1

    def _validate(self, name: str, country: str):
        name = name.strip()
        country = country.strip().upper()

        if not name:
            raise ArenaError("Arena name cannot be empty.")
        if not self.country_api.exists(country):
            raise ArenaError(f'Country code "{country}" was not found in countries.csv.')

        return name, country

    def add(self, name: str, country: str) -> dict:
        name, country = self._validate(name, country)

        new_row = {"arena_id": self._next_id(), "name": name, "country": country}
        existing = self.get_all()
        existing.append(new_row)
        self._save_all(existing)
        return new_row

    def update(self, arena_id: int, name: str, country: str) -> None:
        name, country = self._validate(name, country)

        existing = self.get_all()
        if not any(row["arena_id"] == arena_id for row in existing):
            raise ArenaError(f"No arena found with ArenaID {arena_id}.")

        others = [row for row in existing if row["arena_id"] != arena_id]
        others.append({"arena_id": arena_id, "name": name, "country": country})
        self._save_all(others)

    def delete(self, arena_id: int) -> None:
        existing = self.get_all()
        remaining = [row for row in existing if row["arena_id"] != arena_id]

        if len(remaining) == len(existing):
            raise ArenaError(f"No arena found with ArenaID {arena_id}.")

        self._save_all(remaining)
