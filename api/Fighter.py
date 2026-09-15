import csv
import os

from datetime import datetime

from api.Country import Country
from api.Weight_Classes import WeightClasses

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FIGHTERS_FILE = os.path.join(DATA_DIR, "fighters.csv")

FIELDNAMES = [
    "FighterID",
    "FirstName", "LastName", "Nickname", "Placement",
    "Hometown", "Country",
    "Birthdate",
    "Weightclass", "Reach",
    "Stance", "Style",
]

PLACEMENTS = ["Prefix", "Middle", "Suffix", "None"]

STANCE_TO_INT = {"Orthodox": 0, "Southpaw": 1}
INT_TO_STANCE = {v: k for k, v in STANCE_TO_INT.items()}

STYLE_TO_INT = {"In Fighter": 1, "Out Boxer": 2, "Brawler": 3, "Boxer Puncher": 4}
INT_TO_STYLE = {v: k for k, v in STYLE_TO_INT.items()}

MIN_REACH = 63
MAX_REACH = 75

BIRTHDATE_FORMAT = "%d-%m-%Y"

class FighterError(Exception):
    """Raised when a fighter record fails validation"""
    pass


class Fighter:
    def __init__(self, filepath: str = FIGHTERS_FILE):
        self.filepath = filepath
        self.country_api = Country()
        self.weight_class_api = WeightClasses()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()

    # --- CREATE ---
    def add(self, first_name, last_name, nickname, placement, hometown,
            country, birthdate, weightclass, reach, stance, style) -> dict:
        first_name, last_name, nickname, hometown, country = self._validate(
            first_name, last_name, nickname, placement, hometown,
            country, birthdate, weightclass, reach, stance, style,
        )

        new_row = {
            "fighter_id": self._next_id(),
            "first_name": first_name,
            "last_name": last_name,
            "nickname": nickname,
            "placement": placement,
            "hometown": hometown,
            "country": country,
            "birthdate": birthdate,
            "weightclass": weightclass,
            "reach": reach,
            "stance": stance,
            "style": style,
        }

        existing = self.get_all()
        existing.append(new_row)
        self._save_all(existing)
        return new_row

    # --- READ ---
    def get_all(self) -> list:
        self._ensure_file_exists()
        with open(self.filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [self._row_from_csv(row) for row in reader]
        return sorted(rows, key=lambda r: r["fighter_id"])

    def get_by_id(self, fighter_id: int):
        for row in self.get_all():
            if row["fighter_id"] == fighter_id:
                return row
        return None

    def search_by_name(self, first_name: str = "", last_name: str = "") -> list:
        """Case-insensitive substring match on first and/or last name."""
        first_name = first_name.strip().lower()
        last_name = last_name.strip().lower()

        results = []
        for row in self.get_all():
            if first_name and first_name not in row["first_name"].lower():
                continue
            if last_name and last_name not in row["last_name"].lower():
                continue
            results.append(row)
        return results

    # --- UPDATE ---
    def update(self, fighter_id, first_name, last_name, nickname, placement, hometown,
               country, birthdate, weightclass, reach, stance, style) -> None:
        first_name, last_name, nickname, hometown, country = self._validate(
            first_name, last_name, nickname, placement, hometown,
            country, birthdate, weightclass, reach, stance, style,
        )

        existing = self.get_all()
        if not any(row["fighter_id"] == fighter_id for row in existing):
            raise FighterError(f"No fighter found with FighterID {fighter_id}.")

        others = [row for row in existing if row["fighter_id"] != fighter_id]
        others.append(
            {
                "fighter_id": fighter_id,
                "first_name": first_name,
                "last_name": last_name,
                "nickname": nickname,
                "placement": placement,
                "hometown": hometown,
                "country": country,
                "birthdate": birthdate,
                "weightclass": weightclass,
                "reach": reach,
                "stance": stance,
                "style": style,
            }
        )
        self._save_all(others)

    def _save_all(self, rows: list):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["fighter_id"]):
                writer.writerow(self._row_to_csv(row))

    @staticmethod
    def _row_from_csv(row: dict) -> dict:
        return {
            "fighter_id": int(row["FighterID"]),
            "first_name": row["FirstName"],
            "last_name": row["LastName"],
            "nickname": row["Nickname"],
            "placement": row["Placement"],
            "hometown": row["Hometown"],
            "country": row["Country"],
            "birthdate": row["Birthdate"],
            "weightclass": int(row["Weightclass"]),
            "reach": int(row["Reach"]),
            "stance": int(row["Stance"]),
            "style": int(row["Style"]),
        }

    @staticmethod
    def _row_to_csv(row: dict) -> dict:
        return {
            "FighterID": row["fighter_id"],
            "FirstName": row["first_name"],
            "LastName": row["last_name"],
            "Nickname": row["nickname"],
            "Placement": row["placement"],
            "Hometown": row["hometown"],
            "Country": row["country"],
            "Birthdate": row["birthdate"],
            "Weightclass": row["weightclass"],
            "Reach": row["reach"],
            "Stance": row["stance"],
            "Style": row["style"],
        }

    def _next_id(self) -> int:
        existing = self.get_all()
        if not existing:
            return 1
        return max(row["fighter_id"] for row in existing) + 1

    def _validate(self, first_name, last_name, nickname, placement, hometown,
                  country, birthdate, weightclass, reach, stance, style):
        first_name = first_name.strip()
        last_name = last_name.strip()
        nickname = nickname.strip()
        hometown = hometown.strip()
        country = country.strip().upper()

        if not first_name:
            raise FighterError("First name cannot be empty.")
        if not last_name:
            raise FighterError("Last name cannot be empty.")
        if not hometown:
            raise FighterError("Hometown cannot be empty.")

        if placement not in PLACEMENTS:
            raise FighterError(f"Placement must be one of {PLACEMENTS}.")
        if placement != "None" and not nickname:
            raise FighterError("A placement was chosen but no nickname was given.")
        if placement == "None" and nickname:
            raise FighterError('A nickname was given but Placement is "None" -- pick a placement.')

        if not self.country_api.exists(country):
            raise FighterError(f'Country code "{country}" was not found in countries.csv.')

        try:
            datetime.strptime(birthdate, BIRTHDATE_FORMAT)
        except ValueError:
            raise FighterError('Birthdate must be a valid date in "dd-mm-yyyy" format.')

        valid_weight_limits = [wc["weight_limit"] for wc in self.weight_class_api.get_all()]
        if weightclass not in valid_weight_limits:
            raise FighterError(f"Weightclass {weightclass} does not match any defined weight class.")

        if not (MIN_REACH <= reach <= MAX_REACH):
            raise FighterError(f"Reach must be between {MIN_REACH} and {MAX_REACH} inches (inclusive).")

        if stance not in (0, 1):
            raise FighterError("Stance must be Orthodox (0) or Southpaw (1).")

        if style not in (1, 2, 3, 4):
            raise FighterError("Style must be one of: In Fighter, Out Boxer, Brawler, Boxer Puncher.")

        return first_name, last_name, nickname, hometown, country  

    # --- DELETE ---
    def delete(self, fighter_id: int) -> None:
        existing = self.get_all()
        remaining = [row for row in existing if row["fighter_id"] != fighter_id]

        if len(remaining) == len(existing):
            raise FighterError(f"No fighter found with FighterID {fighter_id}.")

        self._save_all(remaining)
