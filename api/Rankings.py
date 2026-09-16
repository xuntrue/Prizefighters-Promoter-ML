"""
Rankings.py

Monthly ranking snapshots, stored in data/rankings/.

Two files, both in long format (one row per ranked fighter) so they can
be loaded straight into pandas with a single read_csv() -- no globbing
or concatenating per-month files:

    rankings.csv      -- divisional and pound-for-pound rankings
        SnapshotMonth  -> str, "YYYY-MM"
        RankingType    -> "DIVISION" or "P4P"
        WeightLimit    -> int (blank for P4P), FK -> weights.csv
        Rank           -> int, 1..N, contiguous within a snapshot
        FighterID      -> int, FK -> fighters.csv
        Wins/Knockouts/Losses/Draws -> int, the fighter's record AS OF
                          this snapshot (records.csv only holds current
                          values, so these are stored for historical
                          analysis)
        Title          -> int 0/1, does this fighter hold a belt in this
                          division. Deliberately independent of Rank --
                          a champion can be ranked below a #1 contender,
                          and a division can have multiple title holders
                          (e.g. a champion moving up and bringing a belt).

    fan_rankings.csv  -- top 9 fan favourites by Total Fans
        SnapshotMonth  -> str, "YYYY-MM"
        Rank           -> int, 1..9
        FighterID      -> int, FK -> fighters.csv
        TotalFans      -> int
        Wins/Knockouts/Losses/Draws -> int, record as of this snapshot

Kept in a separate file because fan rankings carry TotalFans, have no
Title concept, and are capped at 9 -- folding them into rankings.csv
would mean a mostly-empty column and a RankingType that behaves
differently from the others.
"""

import csv
import os
import re

from api.Fighter import Fighter
from api.Records import Records

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
RANKINGS_DIR = os.path.join(DATA_DIR, "rankings")
RANKINGS_FILE = os.path.join(RANKINGS_DIR, "rankings.csv")
FAN_RANKINGS_FILE = os.path.join(RANKINGS_DIR, "fan_rankings.csv")

RANKING_FIELDNAMES = [
    "SnapshotMonth", "RankingType", "WeightLimit", "Rank", "FighterID",
    "Wins", "Knockouts", "Losses", "Draws", "Title",
]
FAN_FIELDNAMES = [
    "SnapshotMonth", "Rank", "FighterID", "TotalFans",
    "Wins", "Knockouts", "Losses", "Draws",
]

TYPE_DIVISION = "DIVISION"
TYPE_P4P = "P4P"

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

MAX_FAN_RANKS = 9


class RankingError(Exception):
    """Raised when a ranking snapshot fails validation."""
    pass


def validate_month(month: str) -> str:
    month = (month or "").strip()
    if not MONTH_PATTERN.match(month):
        raise RankingError('Snapshot month must be in "YYYY-MM" format (e.g. "2026-03").')
    return month


def _validate_record(wins, knockouts, losses, draws):
    if min(wins, knockouts, losses, draws) < 0:
        raise RankingError("Record values cannot be negative.")
    if knockouts > wins:
        raise RankingError("Knockouts cannot exceed total wins.")


class Rankings:
    """Read/write monthly ranking snapshots."""

    def __init__(self, rankings_file: str = RANKINGS_FILE, fan_file: str = FAN_RANKINGS_FILE,
                 fighter_api: Fighter = None, records_api: Records = None):
        self.rankings_file = rankings_file
        self.fan_file = fan_file
        self.fighter_api = fighter_api or Fighter()
        self.records_api = records_api or Records()
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        os.makedirs(os.path.dirname(self.rankings_file), exist_ok=True)
        for path, fieldnames in ((self.rankings_file, RANKING_FIELDNAMES),
                                 (self.fan_file, FAN_FIELDNAMES)):
            if not os.path.exists(path):
                with open(path, "w", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=fieldnames).writeheader()

    # ================= Division / P4P rankings =================

    def get_all(self) -> list:
        self._ensure_files_exist()
        with open(self.rankings_file, newline="", encoding="utf-8") as f:
            return [
                {
                    "month": row["SnapshotMonth"],
                    "ranking_type": row["RankingType"],
                    "weight_limit": int(row["WeightLimit"]) if row["WeightLimit"] else None,
                    "rank": int(row["Rank"]),
                    "fighter_id": int(row["FighterID"]),
                    "wins": int(row["Wins"]),
                    "knockouts": int(row["Knockouts"]),
                    "losses": int(row["Losses"]),
                    "draws": int(row["Draws"]),
                    "title": int(row["Title"]),
                }
                for row in csv.DictReader(f)
            ]

    def get_snapshot(self, month: str, ranking_type: str, weight_limit=None) -> list:
        """Return the ranked entries for one division (or P4P) in one month."""
        return sorted(
            [
                r for r in self.get_all()
                if r["month"] == month
                and r["ranking_type"] == ranking_type
                and r["weight_limit"] == weight_limit
            ],
            key=lambda r: r["rank"],
        )

    def get_months(self, ranking_type: str = None, weight_limit=None) -> list:
        """All snapshot months present, newest last."""
        rows = self.get_all()
        if ranking_type is not None:
            rows = [r for r in rows if r["ranking_type"] == ranking_type
                    and r["weight_limit"] == weight_limit]
        return sorted({r["month"] for r in rows})

    def get_latest_month(self, ranking_type: str = None, weight_limit=None):
        months = self.get_months(ranking_type, weight_limit)
        return months[-1] if months else None

    def _save_all(self, rows: list):
        with open(self.rankings_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RANKING_FIELDNAMES)
            writer.writeheader()
            ordered = sorted(
                rows,
                key=lambda r: (r["month"], r["ranking_type"], r["weight_limit"] or 0, r["rank"]),
            )
            for row in ordered:
                writer.writerow({
                    "SnapshotMonth": row["month"],
                    "RankingType": row["ranking_type"],
                    "WeightLimit": "" if row["weight_limit"] is None else row["weight_limit"],
                    "Rank": row["rank"],
                    "FighterID": row["fighter_id"],
                    "Wins": row["wins"],
                    "Knockouts": row["knockouts"],
                    "Losses": row["losses"],
                    "Draws": row["draws"],
                    "Title": row["title"],
                })

    def save_snapshot(self, month: str, ranking_type: str, entries: list, weight_limit=None) -> None:
        """
        Replace the snapshot for one division (or P4P) in one month.

        `entries` is an ordered list (index 0 = rank #1) of dicts with
        keys: fighter_id, wins, knockouts, losses, draws, title.
        Ranks are assigned from the list order, so they're always
        contiguous 1..N by construction.
        """
        month = validate_month(month)

        if ranking_type not in (TYPE_DIVISION, TYPE_P4P):
            raise RankingError(f"Ranking type must be {TYPE_DIVISION} or {TYPE_P4P}.")
        if ranking_type == TYPE_DIVISION and weight_limit is None:
            raise RankingError("A divisional ranking needs a weight limit.")
        if ranking_type == TYPE_P4P:
            weight_limit = None

        seen = set()
        validated = []
        for index, entry in enumerate(entries, start=1):
            fighter_id = int(entry["fighter_id"])

            if fighter_id in seen:
                raise RankingError(f"FighterID {fighter_id} appears more than once in this ranking.")
            seen.add(fighter_id)

            fighter = self.fighter_api.get_by_id(fighter_id)
            if fighter is None:
                raise RankingError(f"No fighter found with FighterID {fighter_id}.")

            # Only fighters registered to this division may be ranked in it.
            if ranking_type == TYPE_DIVISION and fighter["weightclass"] != weight_limit:
                raise RankingError(
                    f'{fighter["first_name"]} {fighter["last_name"]} does not compete at '
                    f"{weight_limit} lbs and cannot be ranked in that division."
                )

            wins = int(entry.get("wins", 0))
            knockouts = int(entry.get("knockouts", 0))
            losses = int(entry.get("losses", 0))
            draws = int(entry.get("draws", 0))
            _validate_record(wins, knockouts, losses, draws)

            validated.append({
                "month": month,
                "ranking_type": ranking_type,
                "weight_limit": weight_limit,
                "rank": index,
                "fighter_id": fighter_id,
                "wins": wins,
                "knockouts": knockouts,
                "losses": losses,
                "draws": draws,
                "title": 1 if entry.get("title") else 0,
            })

        others = [
            r for r in self.get_all()
            if not (r["month"] == month
                    and r["ranking_type"] == ranking_type
                    and r["weight_limit"] == weight_limit)
        ]
        self._save_all(others + validated)

    def delete_snapshot(self, month: str, ranking_type: str, weight_limit=None) -> None:
        existing = self.get_all()
        remaining = [
            r for r in existing
            if not (r["month"] == month
                    and r["ranking_type"] == ranking_type
                    and r["weight_limit"] == weight_limit)
        ]
        if len(remaining) == len(existing):
            raise RankingError("No snapshot found for that month/division.")
        self._save_all(remaining)

    # ================= Fan rankings =================

    def get_all_fan_rankings(self) -> list:
        self._ensure_files_exist()
        with open(self.fan_file, newline="", encoding="utf-8") as f:
            return [
                {
                    "month": row["SnapshotMonth"],
                    "rank": int(row["Rank"]),
                    "fighter_id": int(row["FighterID"]),
                    "total_fans": int(row["TotalFans"]),
                    "wins": int(row["Wins"]),
                    "knockouts": int(row["Knockouts"]),
                    "losses": int(row["Losses"]),
                    "draws": int(row["Draws"]),
                }
                for row in csv.DictReader(f)
            ]

    def get_fan_snapshot(self, month: str) -> list:
        return sorted(
            [r for r in self.get_all_fan_rankings() if r["month"] == month],
            key=lambda r: r["rank"],
        )

    def get_fan_months(self) -> list:
        return sorted({r["month"] for r in self.get_all_fan_rankings()})

    def get_latest_fan_month(self):
        months = self.get_fan_months()
        return months[-1] if months else None

    def _save_all_fan_rankings(self, rows: list):
        with open(self.fan_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FAN_FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: (r["month"], r["rank"])):
                writer.writerow({
                    "SnapshotMonth": row["month"],
                    "Rank": row["rank"],
                    "FighterID": row["fighter_id"],
                    "TotalFans": row["total_fans"],
                    "Wins": row["wins"],
                    "Knockouts": row["knockouts"],
                    "Losses": row["losses"],
                    "Draws": row["draws"],
                })

    def save_fan_snapshot(self, month: str, entries: list) -> None:
        """
        Replace the fan-favourite snapshot for one month. `entries` is an
        ordered list (index 0 = rank #1, max 9) of dicts with keys:
        fighter_id, total_fans, wins, knockouts, losses, draws.
        """
        month = validate_month(month)

        if len(entries) > MAX_FAN_RANKS:
            raise RankingError(f"Fan rankings hold at most {MAX_FAN_RANKS} fighters.")

        seen = set()
        validated = []
        for index, entry in enumerate(entries, start=1):
            fighter_id = int(entry["fighter_id"])

            if fighter_id in seen:
                raise RankingError(f"FighterID {fighter_id} appears more than once in the fan rankings.")
            seen.add(fighter_id)

            if self.fighter_api.get_by_id(fighter_id) is None:
                raise RankingError(f"No fighter found with FighterID {fighter_id}.")

            total_fans = int(entry.get("total_fans", 0))
            if total_fans < 0:
                raise RankingError("Total Fans cannot be negative.")

            wins = int(entry.get("wins", 0))
            knockouts = int(entry.get("knockouts", 0))
            losses = int(entry.get("losses", 0))
            draws = int(entry.get("draws", 0))
            _validate_record(wins, knockouts, losses, draws)

            validated.append({
                "month": month, "rank": index, "fighter_id": fighter_id,
                "total_fans": total_fans, "wins": wins, "knockouts": knockouts,
                "losses": losses, "draws": draws,
            })

        others = [r for r in self.get_all_fan_rankings() if r["month"] != month]
        self._save_all_fan_rankings(others + validated)

    def delete_fan_snapshot(self, month: str) -> None:
        existing = self.get_all_fan_rankings()
        remaining = [r for r in existing if r["month"] != month]
        if len(remaining) == len(existing):
            raise RankingError(f"No fan ranking snapshot found for {month}.")
        self._save_all_fan_rankings(remaining)

    # ================= Carry-forward =================

    def _current_record(self, fighter_id: int) -> dict:
        """Current record from records.csv, or zeros if none on file."""
        record = self.records_api.get_by_fighter_id(fighter_id)
        if record is None:
            return {"wins": 0, "knockouts": 0, "losses": 0, "draws": 0}
        return {k: record[k] for k in ("wins", "knockouts", "losses", "draws")}

    def carry_forward(self, ranking_type: str, weight_limit=None, from_month: str = None) -> dict:
        """
        Build a starting point for a new month's snapshot from the most
        recent existing one.

        Fighters who no longer exist, or (for divisional rankings) who
        have since changed weight class, are dropped -- everyone below
        them moves up, so ranks stay contiguous. Records are refreshed
        from records.csv, since the new snapshot should capture the
        fighter's record as of now, not as of last month.

        Returns {"source_month": str|None, "entries": [...], "dropped": [...]}
        where `dropped` describes who was removed and why, so the UI can
        tell the user rather than silently losing a fighter.
        """
        if ranking_type == TYPE_P4P:
            weight_limit = None

        source_month = from_month or self.get_latest_month(ranking_type, weight_limit)
        if source_month is None:
            return {"source_month": None, "entries": [], "dropped": []}

        entries, dropped = [], []
        for row in self.get_snapshot(source_month, ranking_type, weight_limit):
            fighter = self.fighter_api.get_by_id(row["fighter_id"])

            if fighter is None:
                dropped.append({
                    "fighter_id": row["fighter_id"], "previous_rank": row["rank"],
                    "reason": "no longer exists in fighters.csv",
                })
                continue

            if ranking_type == TYPE_DIVISION and fighter["weightclass"] != weight_limit:
                dropped.append({
                    "fighter_id": row["fighter_id"], "previous_rank": row["rank"],
                    "name": f'{fighter["first_name"]} {fighter["last_name"]}',
                    "reason": f'now competes at {fighter["weightclass"]} lbs',
                })
                continue

            entries.append({
                "fighter_id": row["fighter_id"],
                "title": row["title"],
                **self._current_record(row["fighter_id"]),
            })

        return {"source_month": source_month, "entries": entries, "dropped": dropped}

    def carry_forward_fans(self, from_month: str = None) -> dict:
        """Same idea as carry_forward(), for the fan rankings. Total Fans
        is carried over from last month as a starting value for the user
        to overwrite."""
        source_month = from_month or self.get_latest_fan_month()
        if source_month is None:
            return {"source_month": None, "entries": [], "dropped": []}

        entries, dropped = [], []
        for row in self.get_fan_snapshot(source_month):
            if self.fighter_api.get_by_id(row["fighter_id"]) is None:
                dropped.append({
                    "fighter_id": row["fighter_id"], "previous_rank": row["rank"],
                    "reason": "no longer exists in fighters.csv",
                })
                continue

            entries.append({
                "fighter_id": row["fighter_id"],
                "total_fans": row["total_fans"],
                **self._current_record(row["fighter_id"]),
            })

        return {"source_month": source_month, "entries": entries, "dropped": dropped}
