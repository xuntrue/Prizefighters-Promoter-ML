"""
Gyms.py

CRUD + validation for gyms stored in data/gyms.csv.

Columns:
    id                 -> int, auto-assigned (sequential, starting at 1), primary key
    name               -> str
    location           -> str, A-2 code, foreign key -> countries.csv
    trainingCoach      -> int, 0-10 inclusive
    conditioningCoach  -> int, 0-10 inclusive
    fightPromoter      -> int, 0-10 inclusive

The three coach/promoter ratings only matter for later data analysis --
nothing in the UI surfaces them directly (see record_fight_result.py,
which only needs a gym's name for the cornering-gym dropdown).

Like Arenas, no dedicated "add gym" screen was requested -- gyms get
added from the Gyms section in ui/settings.py.
"""

import csv
import os

from api.Country import Country

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
GYMS_FILE = os.path.join(DATA_DIR, "gyms.csv")

FIELDNAMES = ["id", "name", "location", "trainingCoach", "conditioningCoach", "fightPromoter"]

MIN_GYM_RATING = 0
MAX_GYM_RATING = 10


class GymError(Exception):
    """Raised when a gym entry fails validation."""
    pass


class Gyms:
    """CRUD for gyms stored in gyms.csv."""

    def __init__(self, filepath: str = GYMS_FILE, country_api: Country = None):
        self.filepath = filepath
        self.country_api = country_api or Country()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()

    def get_all(self) -> list:
        """Return all gyms as a list of dicts, sorted by name (matches the
        alphabetical ordering the cornering-gym dropdown wants)."""
        self._ensure_file_exists()
        with open(self.filepath, newline="", encoding="utf-8") as f:
            rows = [
                {
                    "id": int(row["id"]),
                    "name": row["name"],
                    "location": row["location"],
                    "training_coach": int(row["trainingCoach"]),
                    "conditioning_coach": int(row["conditioningCoach"]),
                    "fight_promoter": int(row["fightPromoter"]),
                }
                for row in csv.DictReader(f)
            ]
        return sorted(rows, key=lambda r: r["name"].lower())

    def get_by_id(self, gym_id: int):
        for row in self.get_all():
            if row["id"] == gym_id:
                return row
        return None

    def exists(self, gym_id: int) -> bool:
        return self.get_by_id(gym_id) is not None

    def _save_all(self, rows: list):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["id"]):
                writer.writerow({
                    "id": row["id"],
                    "name": row["name"],
                    "location": row["location"],
                    "trainingCoach": row["training_coach"],
                    "conditioningCoach": row["conditioning_coach"],
                    "fightPromoter": row["fight_promoter"],
                })

    def _next_id(self) -> int:
        existing = self.get_all()
        if not existing:
            return 1
        return max(row["id"] for row in existing) + 1

    def _validate(self, name, location, training_coach, conditioning_coach, fight_promoter):
        name = name.strip()
        location = location.strip().upper()

        if not name:
            raise GymError("Gym name cannot be empty.")
        if not self.country_api.exists(location):
            raise GymError(f'Country code "{location}" was not found in countries.csv.')

        for label, value in (("Training Coach", training_coach),
                             ("Conditioning Coach", conditioning_coach),
                             ("Fight Promoter", fight_promoter)):
            if not (MIN_GYM_RATING <= value <= MAX_GYM_RATING):
                raise GymError(f"{label} rating must be between {MIN_GYM_RATING} and {MAX_GYM_RATING}.")

        return name, location

    def add(self, name: str, location: str, training_coach: int,
            conditioning_coach: int, fight_promoter: int) -> dict:
        name, location = self._validate(name, location, training_coach, conditioning_coach, fight_promoter)

        new_row = {
            "id": self._next_id(), "name": name, "location": location,
            "training_coach": training_coach, "conditioning_coach": conditioning_coach,
            "fight_promoter": fight_promoter,
        }
        existing = self.get_all()
        existing.append(new_row)
        self._save_all(existing)
        return new_row

    def update(self, gym_id: int, name: str, location: str, training_coach: int,
              conditioning_coach: int, fight_promoter: int) -> None:
        name, location = self._validate(name, location, training_coach, conditioning_coach, fight_promoter)

        existing = self.get_all()
        if not any(row["id"] == gym_id for row in existing):
            raise GymError(f"No gym found with id {gym_id}.")

        others = [row for row in existing if row["id"] != gym_id]
        others.append({
            "id": gym_id, "name": name, "location": location,
            "training_coach": training_coach, "conditioning_coach": conditioning_coach,
            "fight_promoter": fight_promoter,
        })
        self._save_all(others)

    def delete(self, gym_id: int) -> None:
        existing = self.get_all()
        remaining = [row for row in existing if row["id"] != gym_id]

        if len(remaining) == len(existing):
            raise GymError(f"No gym found with id {gym_id}.")

        self._save_all(remaining)
