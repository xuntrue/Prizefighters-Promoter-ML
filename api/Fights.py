"""
Fights.py

CRUD for fights. Two layers of storage, deliberately kept in sync:

    data/fights.csv         -- compressed index. One row per fight with
                               only the fields needed to search/filter
                               without opening every JSON file:
                                   FightID, RedCornerFighterID,
                                   BlueCornerFighterID, WeightClass,
                                   Date, Championship, Status

    data/fights/<FightID>.json -- full detail file for one fight. Holds
                               everything else: sanctioned rounds/round
                               length now, and pre-fight ("meta") and
                               post-fight ("result") data added by later
                               screens not built yet. Kept mostly empty
                               until those screens exist.

FightID is a 6-digit hex string (e.g. "00001A"), assigned sequentially
from the highest existing ID in fights.csv -- fights.csv is always kept
in sync with fights/, so it's the cheaper source of truth to scan
(reading one CSV vs. listing/opening potentially tens of thousands of
JSON files).

Status lifecycle: Scheduled -> Evented -> Meta -> Complete, with a
separate Cancelled status for bouts that fall through. A cancelled
fight's JSON file and CSV row are both KEPT (status flips to
"Cancelled") rather than deleted, since "I scheduled and then cancelled
this" is itself a fact worth keeping for analysis later. Genuine
mis-clicks can be removed outright with delete(), but only while a
fight is still in Scheduled status -- once a fight has been added to an
event, had meta recorded, or been completed, deleting it outright would
corrupt an event card or a historical record, so delete() refuses.
"""

import csv
import json
import os
from datetime import datetime

from api.Fighter import Fighter

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
FIGHTS_CSV = os.path.join(DATA_DIR, "fights.csv")
FIGHTS_DIR = os.path.join(DATA_DIR, "fights")

CSV_FIELDNAMES = [
    "FightID", "RedCornerFighterID", "BlueCornerFighterID",
    "WeightClass", "Date", "Championship", "Status",
]

DATE_FORMAT = "%d-%m-%Y"

VALID_ROUNDS = (3, 4, 6, 8, 10, 12)
VALID_ROUND_MINUTES = (1, 2, 3)

STATUS_SCHEDULED = "Scheduled"
STATUS_EVENTED = "Evented"
STATUS_META = "Meta"
STATUS_COMPLETE = "Complete"
STATUS_CANCELLED = "Cancelled"

ALL_STATUSES = (STATUS_SCHEDULED, STATUS_EVENTED, STATUS_META, STATUS_COMPLETE, STATUS_CANCELLED)


class FightError(Exception):
    """Raised when a fight fails validation."""
    pass


class Fights:
    """CRUD for the fights.csv index + fights/<FightID>.json detail files."""

    def __init__(self, csv_path: str = FIGHTS_CSV, json_dir: str = FIGHTS_DIR,
                 fighter_api: Fighter = None):
        self.csv_path = csv_path
        self.json_dir = json_dir
        self.fighter_api = fighter_api or Fighter()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self):
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=CSV_FIELDNAMES).writeheader()

    # ================= Index (fights.csv) =================

    def get_all(self) -> list:
        """Return the compressed index -- fast, doesn't touch fights/."""
        self._ensure_storage_exists()
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            rows = [
                {
                    "fight_id": row["FightID"],
                    "red_corner_fighter_id": int(row["RedCornerFighterID"]),
                    "blue_corner_fighter_id": int(row["BlueCornerFighterID"]),
                    "weight_limit": int(row["WeightClass"]),
                    "date": row["Date"],
                    "championship": int(row["Championship"]),
                    "status": row["Status"],
                }
                for row in csv.DictReader(f)
            ]
        return sorted(rows, key=lambda r: (r["date"], r["fight_id"]))

    def get_by_id(self, fight_id: str):
        fight_id = fight_id.strip().upper()
        for row in self.get_all():
            if row["fight_id"] == fight_id:
                return row
        return None

    def get_by_status(self, status: str) -> list:
        return [r for r in self.get_all() if r["status"] == status]

    def get_by_date(self, date_str: str) -> list:
        return [r for r in self.get_all() if r["date"] == date_str]

    def get_scheduled_on_date(self, date_str: str) -> list:
        """Fights on a given date that are still Scheduled -- i.e. eligible
        to be added to a new event card."""
        return [r for r in self.get_by_date(date_str) if r["status"] == STATUS_SCHEDULED]

    def get_by_fighter(self, fighter_id: int) -> list:
        """Every fight (any status) involving this fighter, in either corner."""
        return [
            r for r in self.get_all()
            if r["red_corner_fighter_id"] == fighter_id or r["blue_corner_fighter_id"] == fighter_id
        ]

    def get_championship_fights(self, weight_limit=None) -> list:
        """Championship-bout fights, optionally restricted to one division --
        the starting point for tracing title lineage."""
        rows = [r for r in self.get_all() if r["championship"]]
        if weight_limit is not None:
            rows = [r for r in rows if r["weight_limit"] == weight_limit]
        return rows

    def _save_all(self, rows: list):
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["fight_id"]):
                writer.writerow({
                    "FightID": row["fight_id"],
                    "RedCornerFighterID": row["red_corner_fighter_id"],
                    "BlueCornerFighterID": row["blue_corner_fighter_id"],
                    "WeightClass": row["weight_limit"],
                    "Date": row["date"],
                    "Championship": row["championship"],
                    "Status": row["status"],
                })

    def _next_fight_id(self) -> str:
        existing = self.get_all()
        if not existing:
            return format(1, "06X")
        max_id = max(int(row["fight_id"], 16) for row in existing)
        return format(max_id + 1, "06X")

    # ================= Detail files (fights/<FightID>.json) =================

    def _json_path(self, fight_id: str) -> str:
        return os.path.join(self.json_dir, f"{fight_id.strip().upper()}.json")

    def get_full(self, fight_id: str):
        """Load the full detail file for one fight, or None if missing."""
        path = self._json_path(fight_id)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _save_full(self, fight_id: str, data: dict):
        with open(self._json_path(fight_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ================= Validation =================

    def _validate_new_fight(self, date_str, weight_limit, red_corner_fighter_id,
                             blue_corner_fighter_id, rounds, round_minutes, championship):
        try:
            datetime.strptime(date_str, DATE_FORMAT)
        except (ValueError, TypeError):
            raise FightError('Date must be a valid date in "dd-mm-yyyy" format.')

        if red_corner_fighter_id == blue_corner_fighter_id:
            raise FightError("Red corner and Blue corner must be two different fighters.")

        red = self.fighter_api.get_by_id(red_corner_fighter_id)
        blue = self.fighter_api.get_by_id(blue_corner_fighter_id)

        if red is None:
            raise FightError(f"No fighter found with FighterID {red_corner_fighter_id} (red corner).")
        if blue is None:
            raise FightError(f"No fighter found with FighterID {blue_corner_fighter_id} (blue corner).")

        if red["weightclass"] != weight_limit:
            raise FightError(
                f'{red["first_name"]} {red["last_name"]} is not registered at {weight_limit} lbs.'
            )
        if blue["weightclass"] != weight_limit:
            raise FightError(
                f'{blue["first_name"]} {blue["last_name"]} is not registered at {weight_limit} lbs.'
            )

        if rounds not in VALID_ROUNDS:
            raise FightError(f"Rounds must be one of {VALID_ROUNDS}.")
        if round_minutes not in VALID_ROUND_MINUTES:
            raise FightError(f"Round length must be one of {VALID_ROUND_MINUTES} minutes.")

    # ================= Mutations =================

    def schedule(self, date: str, weight_limit: int, red_corner_fighter_id: int,
                 blue_corner_fighter_id: int, rounds: int, round_minutes: int,
                 championship: bool = False) -> dict:
        """Create a new fight: writes the fights.csv row AND the full
        fights/<FightID>.json detail file."""
        self._validate_new_fight(
            date, weight_limit, red_corner_fighter_id, blue_corner_fighter_id,
            rounds, round_minutes, championship,
        )

        fight_id = self._next_fight_id()
        championship_flag = 1 if championship else 0

        index_row = {
            "fight_id": fight_id,
            "red_corner_fighter_id": red_corner_fighter_id,
            "blue_corner_fighter_id": blue_corner_fighter_id,
            "weight_limit": weight_limit,
            "date": date,
            "championship": championship_flag,
            "status": STATUS_SCHEDULED,
        }

        existing = self.get_all()
        existing.append(index_row)
        self._save_all(existing)

        full_record = {
            "fight_id": fight_id,
            "red_corner_fighter_id": red_corner_fighter_id,
            "blue_corner_fighter_id": blue_corner_fighter_id,
            "weight_limit": weight_limit,
            "date": date,
            "championship": bool(championship),
            "rounds": rounds,
            "round_minutes": round_minutes,
            "status": STATUS_SCHEDULED,
            "event_id": None,
            "meta": {},
            "result": {},
        }
        self._save_full(fight_id, full_record)

        return index_row

    def update_status(self, fight_id: str, new_status: str) -> None:
        """Flip a fight's status in both the CSV index and its JSON file.
        Used by Events.py (Scheduled -> Evented) and, later, by
        pre-/post-fight recording screens."""
        if new_status not in ALL_STATUSES:
            raise FightError(f"Status must be one of {ALL_STATUSES}.")

        existing = self.get_all()
        match = next((r for r in existing if r["fight_id"] == fight_id.strip().upper()), None)
        if match is None:
            raise FightError(f"No fight found with FightID {fight_id}.")

        match["status"] = new_status
        self._save_all(existing)

        full = self.get_full(fight_id)
        if full is not None:
            full["status"] = new_status
            self._save_full(fight_id, full)

    def set_event_id(self, fight_id: str, event_id) -> None:
        """Record which event a fight belongs to, in its JSON file only --
        fights.csv stays lean and doesn't need this to search/filter."""
        full = self.get_full(fight_id)
        if full is None:
            raise FightError(f"No fight found with FightID {fight_id}.")
        full["event_id"] = event_id
        self._save_full(fight_id, full)

    def cancel(self, fight_id: str) -> None:
        fight = self.get_by_id(fight_id)
        if fight is None:
            raise FightError(f"No fight found with FightID {fight_id}.")
        if fight["status"] == STATUS_CANCELLED:
            raise FightError("That fight is already cancelled.")
        self.update_status(fight_id, STATUS_CANCELLED)

    def delete(self, fight_id: str) -> None:
        """Permanently remove a fight -- only allowed while it's still
        Scheduled, so an Evented/Meta/Complete fight (which other data
        may already reference) can never be deleted out from under it."""
        fight = self.get_by_id(fight_id)
        if fight is None:
            raise FightError(f"No fight found with FightID {fight_id}.")
        if fight["status"] != STATUS_SCHEDULED:
            raise FightError(
                f'Only Scheduled fights can be deleted outright (this one is {fight["status"]}) -- '
                f"use cancel() instead."
            )

        existing = self.get_all()
        remaining = [r for r in existing if r["fight_id"] != fight_id.strip().upper()]
        self._save_all(remaining)

        path = self._json_path(fight_id)
        if os.path.exists(path):
            os.remove(path)
