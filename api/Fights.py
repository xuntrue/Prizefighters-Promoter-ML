import csv
import json
import os
import re

from datetime import datetime

from api.Fighter import Fighter

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
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

    def get_scheduled_rounds(self, fight_id: str):
        """ Get the scheduled rounds for a specific fight """
        fight = self.get_full(fight_id)
        if not fight:
            raise FightError(f"No fight found with FightID {fight_id}.")
        if fight["status"] == (STATUS_CANCELLED):
            raise FightError(f"Fight {fight_id} is not scheduled.")
        return fight.get("rounds", [])

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

    def save_meta(self, fight_id: str, meta: dict) -> None:
        """Overwrite the full meta object (both corners) for one fight.
        Used by PrizefighterAPI.save_fight_meta(), which builds the
        merged {red_corner, blue_corner} dict one corner at a time --
        this module doesn't know anything about the meta schema itself
        (that lives in Fighter.py), it just stores whatever dict it's
        handed under "meta"."""
        full = self.get_full(fight_id)
        if full is None:
            raise FightError(f"No fight found with FightID {fight_id}.")
        full["meta"] = meta
        self._save_full(fight_id, full)

    def save_result(self, fight_id: str, result: dict) -> None:
        """Overwrite the full result object for one fight. Used by
        PrizefighterAPI.save_fight_result() after validate_result() (below)
        has cleaned the data; this method itself doesn't validate anything,
        same division of responsibility as save_meta()."""
        full = self.get_full(fight_id)
        if full is None:
            raise FightError(f"No fight found with FightID {fight_id}.")
        full["result"] = result
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


# =====================================================================
# Post-fight result schema
#
# This defines the shape of fights/<FightID>.json's "result" object --
# see record_fight_result.py, the only thing that writes it, via
# PrizefighterAPI.save_fight_result(). It lives here (not in Fighter.py,
# where the pre-fight "meta" schema lives) because a result is
# fundamentally about what happened IN this fight -- punch stats,
# scorecards, who stopped whom -- not a durable fact about a fighter
# the way attributes/tendencies are. The two corners' post-fight deltas
# (new record, prize money, XP gained, tendency changes) live here too
# for the same reason: they're this fight's outcome, even though they
# go on to affect what a fighter looks like afterward.
#
# {
#   "gyms": {"red_corner": int|None, "blue_corner": int|None},   -- FK -> gyms.csv
#
#   "rounds": {
#     "red_corner": [ {round}, ... ],   -- length == rounds actually fought
#     "blue_corner": [ {round}, ... ],  -- (== stoppage round, or all
#   },                                     sanctioned rounds if it went the distance)
#
#   "scorecards": {
#     "judge_1": {"red_corner": [int|None, ...], "blue_corner": [int|None, ...]},
#     "judge_2": {...}, "judge_3": {...},
#   },   -- each list has length == the fight's SANCTIONED rounds (not just
#          rounds fought); entries from the stoppage round onward are None,
#          since judges don't score a round the fight was stopped in or
#          any round after
#
#   "stoppage": {"round": int, "losing_corner": "red_corner"|"blue_corner",
#                "method": "KO"|"TKO", "time": "2'34\"56"} | None,
#
#   "outcome": {"winner_id": int|None, "method": "KO"|"TKO"|"UD"|"SD"|"MD"},
#     -- winner_id is a FighterID, null only for a drawn decision (UD/SD/MD
#        with no stoppage); a stoppage always has a winner, and
#        outcome.method must match stoppage.method when one exists
#
#   "post_fight": {
#     "red_corner": {post_fight corner block}, "blue_corner": {...},
#   },
# }
#
# One ROUND block (one entry in rounds.red_corner / rounds.blue_corner):
# {
#   "punches": {
#     "jab": {"landed": int, "thrown": int}, "cross": {...},
#     "lead_hook": {...}, "rear_hook": {...},
#     "lead_uppercut": {...}, "rear_uppercut": {...},
#     "head": {...}, "body": {...},          -- must sum to the same
#                                                landed/thrown totals as
#                                                the six punch types above
#     "power": {"landed": int, "thrown": int},  -- COMPUTED, never taken
#                                                   from user input: the
#                                                   sum of the four power
#                                                   punches (hooks + uppercuts)
#     "counter": {"landed": int, "thrown": int},  -- independent of the above
#   },
#   "knocked_down": int,
# }
#
# One POST_FIGHT CORNER block:
# {
#   "new_record": {"wins": int, "knockouts": int, "losses": int, "draws": int},
#   "prize_money": int,   -- >= 0
#   "total_fans": int,    -- >= 0
#   "xp_gained": int,     -- >= 0
#   "tendency_changes": {  -- signed deltas, NOT applied to anything yet
#     "body_head": int, "single_punches_combinations": int, "speed_power": int,
#     "inside_outside": int, "block_dodge": int,
#   },
# }
# =====================================================================

CORNERS = ("red_corner", "blue_corner")
JUDGES = ("judge_1", "judge_2", "judge_3")

PUNCH_TYPE_FIELDS = ["jab", "cross", "lead_hook", "rear_hook", "lead_uppercut", "rear_uppercut"]
TARGET_FIELDS = ["head", "body"]
POWER_COMPONENTS = ["lead_hook", "rear_hook", "lead_uppercut", "rear_uppercut"]
COUNTER_FIELD = "counter"

# Every field a round's "punches" dict has ON DISK, in display order --
# "power" is included here even though it's never read from user input,
# since it's still part of what gets stored.
ALL_PUNCH_STAT_FIELDS = PUNCH_TYPE_FIELDS + TARGET_FIELDS + ["power", COUNTER_FIELD]

STOPPAGE_METHODS = ("KO", "TKO")
DECISION_METHODS = ("UD", "SD", "MD")
OUTCOME_METHODS = STOPPAGE_METHODS + DECISION_METHODS

MIN_ROUND_SCORE = 1
MAX_ROUND_SCORE = 10

# "2'34\"56" -- minutes'seconds"hundredths. Seconds are range-checked
# separately (below) since the regex alone can't enforce 0-59.
STOPPAGE_TIME_PATTERN = re.compile(r'^(\d{1,2})\'(\d{1,2})"(\d{1,3})$')

# The 5 tendencies a post-fight result can shift -- deliberately a subset
# of Fighter.TENDENCY_FIELDS (which also has 4 first/second-half
# aggression splits that a single fight's result doesn't touch).
from api.Fighter import TENDENCY_FIELDS as _ALL_TENDENCY_FIELDS  # noqa: E402
TENDENCY_CHANGE_FIELDS = _ALL_TENDENCY_FIELDS[:5]
MIN_TENDENCY_CHANGE = -100
MAX_TENDENCY_CHANGE = 100


def _validate_punch_field(punches: dict, key: str, label: str, corner: str, round_index: int) -> dict:
    entry = punches.get(key, {})
    try:
        landed = int(entry["landed"])
        thrown = int(entry["thrown"])
    except (KeyError, TypeError, ValueError):
        raise FightError(f"{corner} round {round_index}: {label} landed/thrown must be whole numbers.")
    if landed < 0 or thrown < 0:
        raise FightError(f"{corner} round {round_index}: {label} cannot be negative.")
    if landed > thrown:
        raise FightError(f"{corner} round {round_index}: {label} landed cannot exceed thrown.")
    return {"landed": landed, "thrown": thrown}


def _validate_round_stats(round_data: dict, corner: str, round_index: int) -> dict:
    punches = round_data.get("punches", {})
    cleaned_punches = {}

    for key in PUNCH_TYPE_FIELDS + TARGET_FIELDS:
        cleaned_punches[key] = _validate_punch_field(
            punches, key, key.replace("_", " ").title(), corner, round_index
        )
    cleaned_punches[COUNTER_FIELD] = _validate_punch_field(
        punches, COUNTER_FIELD, "Counter", corner, round_index
    )

    # power is derived -- never taken from user input, so it can never
    # disagree with its own components.
    cleaned_punches["power"] = {
        "landed": sum(cleaned_punches[k]["landed"] for k in POWER_COMPONENTS),
        "thrown": sum(cleaned_punches[k]["thrown"] for k in POWER_COMPONENTS),
    }

    # Cross-axis consistency: every punch is classified by TYPE and by
    # TARGET, so the two axes' totals must agree -- they're two views of
    # the same underlying punches, not independent quantities.
    type_landed = sum(cleaned_punches[k]["landed"] for k in PUNCH_TYPE_FIELDS)
    type_thrown = sum(cleaned_punches[k]["thrown"] for k in PUNCH_TYPE_FIELDS)
    target_landed = sum(cleaned_punches[k]["landed"] for k in TARGET_FIELDS)
    target_thrown = sum(cleaned_punches[k]["thrown"] for k in TARGET_FIELDS)
    if type_landed != target_landed:
        raise FightError(
            f"{corner} round {round_index}: punch-type landed total ({type_landed}) "
            f"doesn't match head+body landed total ({target_landed})."
        )
    if type_thrown != target_thrown:
        raise FightError(
            f"{corner} round {round_index}: punch-type thrown total ({type_thrown}) "
            f"doesn't match head+body thrown total ({target_thrown})."
        )

    try:
        knocked_down = int(round_data.get("knocked_down", 0))
    except (TypeError, ValueError):
        raise FightError(f"{corner} round {round_index}: Knocked Down must be a whole number.")
    if knocked_down < 0:
        raise FightError(f"{corner} round {round_index}: Knocked Down cannot be negative.")

    return {"punches": cleaned_punches, "knocked_down": knocked_down}


def _validate_stoppage(stoppage, sanctioned_rounds: int):
    if stoppage is None:
        return None

    try:
        stoppage_round = int(stoppage["round"])
        losing_corner = stoppage["losing_corner"]
        method = stoppage["method"]
        time_str = stoppage["time"]
    except (KeyError, TypeError, ValueError):
        raise FightError('Stoppage must include "round", "losing_corner", "method", and "time".')

    if not (1 <= stoppage_round <= sanctioned_rounds):
        raise FightError(f"Stoppage round must be between 1 and {sanctioned_rounds}.")
    if losing_corner not in CORNERS:
        raise FightError(f"Stoppage losing_corner must be one of {CORNERS}.")
    if method not in STOPPAGE_METHODS:
        raise FightError(f"Stoppage method must be one of {STOPPAGE_METHODS}.")

    time_match = STOPPAGE_TIME_PATTERN.match(str(time_str).strip())
    if not time_match:
        raise FightError('Stoppage time must look like 2\'34"56 (minutes\'seconds"hundredths).')
    if int(time_match.group(2)) > 59:
        raise FightError("Stoppage time: seconds must be 0-59.")

    return {
        "round": stoppage_round, "losing_corner": losing_corner,
        "method": method, "time": time_str.strip(),
    }


def _validate_scorecards(scorecards: dict, sanctioned_rounds: int, stoppage) -> dict:
    cleaned = {}
    for judge in JUDGES:
        judge_card = scorecards.get(judge, {})
        cleaned_judge = {}
        for corner in CORNERS:
            scores = judge_card.get(corner, [])
            if len(scores) != sanctioned_rounds:
                raise FightError(
                    f"{judge} {corner}: needs an entry for all {sanctioned_rounds} sanctioned rounds "
                    f"(blank for rounds not scored)."
                )
            cleaned_scores = []
            for round_index, score in enumerate(scores, start=1):
                unscored = stoppage is not None and round_index >= stoppage["round"]
                if unscored:
                    if score is not None:
                        raise FightError(
                            f"{judge} {corner} round {round_index}: must be blank -- the fight ended "
                            f'by {stoppage["method"]} in round {stoppage["round"]}.'
                        )
                    cleaned_scores.append(None)
                else:
                    try:
                        score_val = int(score)
                    except (TypeError, ValueError):
                        raise FightError(f"{judge} {corner} round {round_index}: score must be a whole number.")
                    if not (MIN_ROUND_SCORE <= score_val <= MAX_ROUND_SCORE):
                        raise FightError(
                            f"{judge} {corner} round {round_index}: score must be between "
                            f"{MIN_ROUND_SCORE} and {MAX_ROUND_SCORE}."
                        )
                    cleaned_scores.append(score_val)
            cleaned_judge[corner] = cleaned_scores
        cleaned[judge] = cleaned_judge
    return cleaned


def _validate_outcome(outcome: dict, stoppage, red_id: int, blue_id: int) -> dict:
    winner_id = outcome.get("winner_id")
    method = outcome.get("method")

    if method not in OUTCOME_METHODS:
        raise FightError(f"Outcome method must be one of {OUTCOME_METHODS}.")

    if stoppage is not None:
        if method != stoppage["method"]:
            raise FightError("Outcome method must match the stoppage method.")
        expected_winner = blue_id if stoppage["losing_corner"] == "red_corner" else red_id
        if winner_id != expected_winner:
            raise FightError("Outcome winner must be whichever fighter was NOT stopped.")
    else:
        if method not in DECISION_METHODS:
            raise FightError(f"Without a stoppage, outcome method must be one of {DECISION_METHODS}.")
        if winner_id is not None and winner_id not in (red_id, blue_id):
            raise FightError("Outcome winner must be one of this fight's two fighters, or null for a draw.")

    return {"winner_id": winner_id, "method": method}


def _validate_post_fight_corner(data: dict, corner: str) -> dict:
    record = data.get("new_record", {})
    try:
        wins = int(record["wins"])
        knockouts = int(record["knockouts"])
        losses = int(record["losses"])
        draws = int(record["draws"])
    except (KeyError, TypeError, ValueError):
        raise FightError(f"{corner}: new record (wins/knockouts/losses/draws) must be whole numbers.")
    if min(wins, knockouts, losses, draws) < 0:
        raise FightError(f"{corner}: new record values cannot be negative.")
    if knockouts > wins:
        raise FightError(f"{corner}: knockouts cannot exceed wins.")

    try:
        prize_money = int(data["prize_money"])
        total_fans = int(data["total_fans"])
        xp_gained = int(data["xp_gained"])
    except (KeyError, TypeError, ValueError):
        raise FightError(f"{corner}: prize money, total fans, and XP gained must be whole numbers.")
    if min(prize_money, total_fans, xp_gained) < 0:
        raise FightError(f"{corner}: prize money, total fans, and XP gained cannot be negative.")

    tendency_changes = data.get("tendency_changes", {})
    cleaned_changes = {}
    for key, label_a, label_b in TENDENCY_CHANGE_FIELDS:
        try:
            value = int(tendency_changes[key])
        except (KeyError, TypeError, ValueError):
            raise FightError(f'{corner}: "{label_a}/{label_b}" change must be a whole number.')
        if not (MIN_TENDENCY_CHANGE <= value <= MAX_TENDENCY_CHANGE):
            raise FightError(
                f'{corner}: "{label_a}/{label_b}" change must be between '
                f"{MIN_TENDENCY_CHANGE} and {MAX_TENDENCY_CHANGE}."
            )
        cleaned_changes[key] = value

    return {
        "new_record": {"wins": wins, "knockouts": knockouts, "losses": losses, "draws": draws},
        "prize_money": prize_money,
        "total_fans": total_fans,
        "xp_gained": xp_gained,
        "tendency_changes": cleaned_changes,
    }


def validate_result(result: dict, fight: dict) -> dict:
    """
    Validate a fight's full post-fight result block. `fight` is the
    fight's own full JSON record (from Fights.get_full()) -- used to
    bound round counts against the sanctioned distance and cross-check
    the outcome against this fight's two actual fighters. Returns a
    cleaned copy, or raises FightError naming the first problem found.

    Gym existence isn't checked here -- that requires a Gyms instance,
    and this function is a pure structural validator with no other
    module dependencies, same design as Fighter.validate_meta_section().
    The caller (PrizefighterAPI.save_fight_result) checks gym IDs itself.
    """
    sanctioned_rounds = fight["rounds"]
    red_id = fight["red_corner_fighter_id"]
    blue_id = fight["blue_corner_fighter_id"]

    gyms = result.get("gyms", {})
    cleaned_gyms = {
        corner: (None if gyms.get(corner) is None else int(gyms.get(corner)))
        for corner in CORNERS
    }

    stoppage = _validate_stoppage(result.get("stoppage"), sanctioned_rounds)
    rounds_fought = stoppage["round"] if stoppage else sanctioned_rounds

    cleaned_rounds = {}
    rounds_data = result.get("rounds", {})
    for corner in CORNERS:
        corner_rounds = rounds_data.get(corner, [])
        if len(corner_rounds) != rounds_fought:
            raise FightError(
                f"{corner} needs exactly {rounds_fought} round(s) of punch stats "
                f"(this fight went {rounds_fought} round(s))."
            )
        cleaned_rounds[corner] = [
            _validate_round_stats(round_data, corner, round_index)
            for round_index, round_data in enumerate(corner_rounds, start=1)
        ]

    cleaned_scorecards = _validate_scorecards(result.get("scorecards", {}), sanctioned_rounds, stoppage)
    cleaned_outcome = _validate_outcome(result.get("outcome", {}), stoppage, red_id, blue_id)

    post_fight = result.get("post_fight", {})
    cleaned_post_fight = {
        corner: _validate_post_fight_corner(post_fight.get(corner, {}), corner)
        for corner in CORNERS
    }

    return {
        "gyms": cleaned_gyms,
        "rounds": cleaned_rounds,
        "scorecards": cleaned_scorecards,
        "stoppage": stoppage,
        "outcome": cleaned_outcome,
        "post_fight": cleaned_post_fight,
    }
