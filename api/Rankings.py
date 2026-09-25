import csv
import os
import re
from datetime import date

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
    "FighterWeightLimit", "Wins", "Knockouts", "Losses", "Draws", "Title",
]
FAN_FIELDNAMES = [
    "SnapshotMonth", "Rank", "FighterID", "FighterWeightLimit", "TotalFans",
    "Wins", "Knockouts", "Losses", "Draws",
]

TYPE_DIVISION = "DIVISION"
TYPE_P4P = "P4P"

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

MAX_FAN_RANKS = 9

class RankingError(Exception):
    """ Raised when a ranking snapshot fails validation """
    pass

def validate_month(month: str) -> str:
    month = (month or "").strip()
    if not MONTH_PATTERN.match(month):
        raise RankingError('Snapshot month must be in "YYYY-MM" format (e.g. "2026-03").')
    return month

def next_month_str(month: str) -> str:
    """'2026-03' -> '2026-04'; '2026-12' -> '2027-01'."""
    month = validate_month(month)
    year, mon = (int(part) for part in month.split("-"))
    mon += 1
    if mon > 12:
        mon = 1
        year += 1
    return f"{year:04d}-{mon:02d}"

def _validate_record(wins, knockouts, losses, draws):
    if min(wins, knockouts, losses, draws) < 0:
        raise RankingError("Record values cannot be negative.")
    if knockouts > wins:
        raise RankingError("Knockouts cannot exceed total wins.")

class Rankings:
    """ Read/write monthly ranking snapshots"""
    def __init__(self, rankings_file: str = RANKINGS_FILE, fan_file: str = FAN_RANKINGS_FILE, fighter_api: Fighter = None, records_api: Records = None):
        self.rankings_file = rankings_file
        self.fan_file = fan_file
        self.fighter_api = fighter_api or Fighter()
        self.records_api = records_api or Records()
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        os.makedirs(os.path.dirname(self.rankings_file), exist_ok=True)
        for path, fieldnames in ((self.rankings_file, RANKING_FIELDNAMES), (self.fan_file, FAN_FIELDNAMES)):
            if not os.path.exists(path):
                with open(path, "w", newline="", encoding="utf-8") as f:
                    csv.DictWriter(f, fieldnames=fieldnames).writeheader()

    # ================= Division / P4P rankings =================
    def get_all(self) -> list:
        self._ensure_files_exist()
        with open(self.rankings_file, newline="", encoding="utf-8") as f:
            rows = []
            for row in csv.DictReader(f):
                raw_fighter_weight = row.get("FighterWeightLimit")
                rows.append({
                    "month": row["SnapshotMonth"],
                    "ranking_type": row["RankingType"],
                    "weight_limit": int(row["WeightLimit"]) if row["WeightLimit"] else None,
                    "rank": int(row["Rank"]),
                    "fighter_id": int(row["FighterID"]),
                    "fighter_weight_limit": int(raw_fighter_weight) if raw_fighter_weight else None,
                    "wins": int(row["Wins"]),
                    "knockouts": int(row["Knockouts"]),
                    "losses": int(row["Losses"]),
                    "draws": int(row["Draws"]),
                    "title": int(row["Title"]),
                })
            return rows

    def get_snapshot(self, month: str, ranking_type: str, weight_limit=None) -> list:
        """ Return the ranked entries for one division (or P4P) in one month """
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
        """ All snapshot months present, newest last """
        rows = self.get_all()
        if ranking_type is not None:
            rows = [r for r in rows if r["ranking_type"] == ranking_type
                    and r["weight_limit"] == weight_limit]
        return sorted({r["month"] for r in rows})

    def get_latest_month(self, ranking_type: str = None, weight_limit=None):
        months = self.get_months(ranking_type, weight_limit)
        return months[-1] if months else None

    def get_next_month(self, ranking_type: str, weight_limit=None):
        """ The month after the most recent existing snapshot """
        latest = self.get_latest_month(ranking_type, weight_limit)
        return next_month_str(latest) if latest else None

    def get_available_months(self, ranking_type: str, weight_limit=None) -> list:
        """
        Values for the month combobox: every month that actually has a
        saved snapshot for this division/P4P, from earliest to latest,
        plus exactly one extra month after the latest -- so selecting it
        is how the user starts entering a new month's rankings (see
        carry_forward()). If nothing has ever been saved for this
        division/type, returns just today's real calendar month, same
        "game calendar may not match reality" caveat as the age preview
        elsewhere in this app.
        """
        months = self.get_months(ranking_type, weight_limit)
        if not months:
            today = date.today()
            return [f"{today.year:04d}-{today.month:02d}"]
        return months + [next_month_str(months[-1])]

    def get_previous_month(self, ranking_type: str, weight_limit, month: str):
        """
        The most recent EXISTING snapshot month strictly before `month`
        for this division (or P4P) -- skips gaps rather than requiring
        exact calendar adjacency, since divisions can drift out of sync
        with each other (see rankings.py). Returns None if there's no
        earlier snapshot at all, which the caller should treat as "no
        comparison available" rather than "everyone is new."

        String comparison is safe here (month < month) since "YYYY-MM"
        sorts correctly as plain text, unlike this app's "dd-mm-yyyy"
        dates elsewhere.
        """
        earlier = [m for m in self.get_months(ranking_type, weight_limit) if m < month]
        return max(earlier) if earlier else None

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
                    "FighterWeightLimit": (
                        "" if row.get("fighter_weight_limit") is None else row["fighter_weight_limit"]
                    ),
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
        contiguous 1..N by construction. Each entry's division
        (fighter_weight_limit) is looked up from fighters.csv and stored
        automatically -- it isn't something the caller passes in.
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
                # The fighter's own registered division right now. For
                # DIVISION rows this is always == weight_limit (enforced
                # above); for P4P it's the whole point -- weight_limit is
                # blank there, so this is the only place a P4P entry's
                # division gets recorded.
                "fighter_weight_limit": fighter["weightclass"],
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
            rows = []
            for row in csv.DictReader(f):
                raw_fighter_weight = row.get("FighterWeightLimit")
                rows.append({
                    "month": row["SnapshotMonth"],
                    "rank": int(row["Rank"]),
                    "fighter_id": int(row["FighterID"]),
                    "fighter_weight_limit": int(raw_fighter_weight) if raw_fighter_weight else None,
                    "total_fans": int(row["TotalFans"]),
                    "wins": int(row["Wins"]),
                    "knockouts": int(row["Knockouts"]),
                    "losses": int(row["Losses"]),
                    "draws": int(row["Draws"]),
                })
            return rows

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

    def get_next_fan_month(self):
        latest = self.get_latest_fan_month()
        return next_month_str(latest) if latest else None

    def get_available_fan_months(self) -> list:
        """Same idea as get_available_months(), for fan rankings: every
        month with a saved snapshot, plus one extra month after the
        latest for starting a new one. Just today's real calendar month
        if nothing has ever been saved yet."""
        months = self.get_fan_months()
        if not months:
            today = date.today()
            return [f"{today.year:04d}-{today.month:02d}"]
        return months + [next_month_str(months[-1])]

    def get_previous_fan_month(self, month: str):
        """The most recent EXISTING fan-rankings month strictly before
        `month` -- see get_previous_month()'s docstring for why this
        skips gaps rather than requiring exact calendar adjacency."""
        earlier = [m for m in self.get_fan_months() if m < month]
        return max(earlier) if earlier else None

    def _save_all_fan_rankings(self, rows: list):
        with open(self.fan_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FAN_FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: (r["month"], r["rank"])):
                writer.writerow({
                    "SnapshotMonth": row["month"],
                    "Rank": row["rank"],
                    "FighterID": row["fighter_id"],
                    "FighterWeightLimit": (
                        "" if row.get("fighter_weight_limit") is None else row["fighter_weight_limit"]
                    ),
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
        fighter_id, total_fans, wins, knockouts, losses, draws. Each
        entry's division (fighter_weight_limit) is looked up from
        fighters.csv and stored automatically, same as in save_snapshot().
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

            fighter = self.fighter_api.get_by_id(fighter_id)
            if fighter is None:
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
                "fighter_weight_limit": fighter["weightclass"],
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

    # ================= Rank deltas =================

    @staticmethod
    def _rank_deltas_from_snapshot(previous_snapshot: list, current_entries: list) -> dict:
        """
        Shared by compute_rank_deltas() and compute_fan_rank_deltas():
        given a previous month's saved snapshot and the CURRENTLY
        DISPLAYED list of entries in rank order (index 0 = rank #1 --
        this may not be saved yet, e.g. a freshly carried-forward month
        still being edited), works out each fighter's rank change.

        Returns {fighter_id: int delta | "NR"}. A positive delta means
        the fighter moved UP (a better, lower rank number -- #5 -> #2 is
        +3); negative means they dropped. "NR" means the fighter wasn't
        in the previous snapshot at all. A fighter from the previous
        snapshot who's absent from current_entries simply gets no key
        here -- there's no row in the current table to attach a delta
        to, and per the UI spec, a fighter falling out of the rankings
        isn't indicated at all.
        """
        previous_rank_by_fighter = {row["fighter_id"]: row["rank"] for row in previous_snapshot}

        deltas = {}
        for index, entry in enumerate(current_entries or []):
            fighter_id = entry["fighter_id"]
            current_rank = index + 1
            previous_rank = previous_rank_by_fighter.get(fighter_id)
            deltas[fighter_id] = "NR" if previous_rank is None else previous_rank - current_rank
        return deltas

    def compute_rank_deltas(self, ranking_type: str, weight_limit, current_month: str,
                            current_entries: list = None) -> dict:
        """
        Rank deltas for a division (or P4P) snapshot, comparing
        current_entries against the most recent EXISTING month strictly
        before current_month -- which may skip over gaps, since one
        division can drift a month or two ahead of another. Returns {}
        if there's no earlier snapshot to compare against at all (e.g.
        this is the very first month ever recorded for this division),
        which the caller should render as "nothing to show", not as
        every fighter being new.
        """
        if ranking_type == TYPE_P4P:
            weight_limit = None

        previous_month = self.get_previous_month(ranking_type, weight_limit, current_month)
        if previous_month is None:
            return {}

        previous_snapshot = self.get_snapshot(previous_month, ranking_type, weight_limit)
        return self._rank_deltas_from_snapshot(previous_snapshot, current_entries)

    def compute_fan_rank_deltas(self, current_month: str, current_entries: list = None) -> dict:
        """Same idea as compute_rank_deltas(), for fan rankings."""
        previous_month = self.get_previous_fan_month(current_month)
        if previous_month is None:
            return {}

        previous_snapshot = self.get_fan_snapshot(previous_month)
        return self._rank_deltas_from_snapshot(previous_snapshot, current_entries)
