"""
Fighter.py

CRUD + validation for fighters stored in data/fighters.csv.

Columns:
    FighterID    -> int, auto-assigned (sequential, starting at 1), primary key
    FirstName    -> str
    LastName     -> str
    Nickname     -> str (may be empty)
    Placement    -> one of "Prefix", "Middle", "Suffix", "None"
    Hometown     -> str
    Country      -> str, A-2 code, foreign key -> countries.csv
    Birthdate    -> str, "dd-mm-yyyy"
    Weightclass  -> int, weight_limit, foreign key -> weights.csv
    Reach        -> int, 63-75 inclusive (inches)
    Stance       -> int, 0 = Orthodox, 1 = Southpaw
    Style        -> int, 1 = In Fighter, 2 = Out Boxer, 3 = Brawler, 4 = Boxer Puncher

Win/loss record is intentionally NOT stored here -- see Records.py.
This module validates the Country and Weightclass foreign keys against
the Country and WeightClasses modules, but never touches records.csv.
"""

import csv
import os
import re
from datetime import datetime

from api.Country import Country
from api.Weight_Classes import WeightClasses

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
FIGHTERS_FILE = os.path.join(DATA_DIR, "fighters.csv")

FIELDNAMES = [
    "FighterID", "FirstName", "LastName", "Nickname", "Placement",
    "Hometown", "Country", "Birthdate", "Weightclass", "Reach", "Stance", "Style",
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
    """Raised when a fighter record fails validation."""
    pass


def format_full_name(first_name: str, last_name: str, nickname: str = "", placement: str = "None") -> str:
    """
    Build a fighter's display name from their name fields, e.g.:
        format_full_name("Andy", "Ruiz", "The Destroyer", "Middle")  -> "Andy 'The Destroyer' Ruiz"
        format_full_name("Conor", "McGregor", "The Notorious", "Prefix") -> "'The Notorious' Conor McGregor"
        format_full_name("Phillip", "Willems", "The Count", "Suffix") -> "Phillip Willems 'The Count'"
        format_full_name("Logan", "Reed", "", "None") -> "Logan Reed"

    Pure formatting logic (no validation) so it can be reused anywhere a
    fighter's name needs to be displayed -- UI previews, printed cards,
    rankings, exports -- without duplicating the placement rules.
    """
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    nickname = (nickname or "").strip()
    base = f"{first_name} {last_name}".strip()

    if not nickname or placement == "None" or placement not in PLACEMENTS:
        return base

    quoted = f"'{nickname}'"
    if placement == "Prefix":
        return f"{quoted} {base}".strip()
    if placement == "Suffix":
        return f"{base} {quoted}".strip()
    return f"{first_name} {quoted} {last_name}".strip()  # Middle


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_birthdate_readable(birthdate: str):
    """Convert 'dd-mm-yyyy' into e.g. 'August 23rd 1993'. Returns None if
    `birthdate` isn't a valid date in that format."""
    try:
        parsed = datetime.strptime(birthdate, BIRTHDATE_FORMAT)
    except (ValueError, TypeError):
        return None
    return f"{parsed.strftime('%B')} {_ordinal(parsed.day)} {parsed.year}"


def compute_age(birthdate: str, as_of):
    """
    Return (years, months) between a fighter's birthdate ('dd-mm-yyyy')
    and `as_of` (a datetime.date). Returns None if birthdate is invalid
    or `as_of` falls before the birthdate.
    """
    try:
        born = datetime.strptime(birthdate, BIRTHDATE_FORMAT).date()
    except (ValueError, TypeError):
        return None

    if as_of < born:
        return None

    years = as_of.year - born.year
    months = as_of.month - born.month
    days = as_of.day - born.day

    if days < 0:
        months -= 1
    if months < 0:
        years -= 1
        months += 12

    return years, months


class Fighter:
    """CRUD for fighters stored in fighters.csv."""

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

    def delete(self, fighter_id: int) -> None:
        existing = self.get_all()
        remaining = [row for row in existing if row["fighter_id"] != fighter_id]

        if len(remaining) == len(existing):
            raise FighterError(f"No fighter found with FighterID {fighter_id}.")

        self._save_all(remaining)


# =====================================================================
# Pre-fight metadata schema
#
# This defines the shape of one CORNER's entry in a fight's meta object
# (fights/<FightID>.json -> meta.red_corner / meta.blue_corner) -- see
# record_fight_prefight.py, which is the only thing that writes it, via
# PrizefighterAPI.save_fight_meta(). It lives here rather than in
# Fights.py because it's fundamentally about what a fighter IS at a
# point in time, not about the fight itself -- Fights.py stays generic
# and just stores whatever dict it's handed under "meta".
#
# One corner's meta:
#   {
#     "profile": {
#       "weigh_in": int,               -- must fall within [min_weigh_in,
#                                          weight_limit] inclusive, where
#                                          min_weigh_in is derived from the
#                                          division below this one (see
#                                          WeightClasses.get_min_weigh_in)
#       "record": {"wins": int, "knockouts": int, "losses": int, "draws": int},
#       "last_6": [str, ...]           -- up to 6 entries, most recent bout
#                                          first, each like "W-TKO(8)"
#     },
#     "career_stats": {8 non-negative ints, see CAREER_STAT_FIELDS},
#     "attributes": {11 floats 0.5-10.0 in steps of 0.5, see ATTRIBUTE_FIELDS},
#     "skills": {
#       "experience": {"level": int 0-10, "xp": int 0-max_xp_for_level(level)},
#       "signature_traits": {
#         "group_1": {"name": str, "level": int 1-5, "xp": int 0-10} | None,
#         ... same shape for group_2, group_3, group_4
#       }
#     },
#     "tendencies": {9 ints 0-100, see TENDENCY_FIELDS}
#   }
# =====================================================================

CAREER_STAT_FIELDS = [
    ("punches_thrown", "Punches Thrown"),
    ("punches_landed", "Punches Landed"),
    ("punches_taken", "Punches Taken"),
    ("knockdowns", "Knockdowns"),
    ("times_knocked_down", "Times Knocked Down"),
    ("titles_won", "Titles Won"),
    ("titles_defended", "Titles Defended"),
    ("total_fans", "Total Fans"),
]

PHYSICAL_ATTRIBUTE_FIELDS = [
    ("strength", "Strength"),
    ("speed", "Speed"),
    ("stamina", "Stamina"),
    ("endurance", "Endurance"),
    ("chin", "Chin"),
]
PUNCH_ATTRIBUTE_FIELDS = [
    ("jab", "Jab"),
    ("cross", "Cross"),
    ("lead_hook", "Lead Hook"),
    ("rear_hook", "Rear Hook"),
    ("lead_uppercut", "Lead Uppercut"),
    ("rear_uppercut", "Rear Uppercut"),
]
ATTRIBUTE_FIELDS = PHYSICAL_ATTRIBUTE_FIELDS + PUNCH_ATTRIBUTE_FIELDS

MIN_ATTRIBUTE = 0.5
MAX_ATTRIBUTE = 10.0
ATTRIBUTE_STEP = 0.5

MIN_LEVEL = 0
MAX_LEVEL = 10
MIN_XP = 0

def max_xp_for_level(level: int) -> int:
    return 100 * (level + 1)

# Signature traits: up to one pick per group, any group may be None.
SIGNATURE_TRAIT_GROUPS = {
    "group_1": ["Agile", "Extra Padding", "Heart", "Invigorate", "Rage",
                "Recovery", "Thick Skin", "Warmed Up"],
    "group_2": ["Body Blows", "Combo Puncher", "Counter Puncher", "Evasive",
                "Hard Core", "Iron Jaw"],
    "group_3": ["Breathing", "Exhaust", "Fan Favourite", "Iron Fists",
                "Show Stopper", "Wolverine"],
    "group_4": ["Rapid Jabs", "Liver Shot", "Powerful Hooks", "Weaving Uppercut"],
}

# Each individual signature trait has its own level (1-5) and XP progress
# (0-10) -- separate from the fighter's overall experience level/XP above.
MIN_TRAIT_LEVEL = 0
MAX_TRAIT_LEVEL = 5
MIN_TRAIT_XP = 0
MAX_TRAIT_XP = 10

# (key, "A" label, "B" label) -- value is 0-100, 0 = pure A, 100 = pure B.
TENDENCY_FIELDS = [
    ("body_head", "Body", "Head"),
    ("single_punches_combinations", "Single Punches", "Combinations"),
    ("speed_power", "Speed", "Power"),
    ("inside_outside", "Inside", "Outside"),
    ("block_dodge", "Block", "Dodge"),
    ("counter_aggressive_first_half", "Counter (First Half)", "Aggressive (First Half)"),
    ("cautious_reckless_first_half", "Cautious (First Half)", "Reckless (First Half)"),
    ("counter_aggressive_second_half", "Counter (Second Half)", "Aggressive (Second Half)"),
    ("cautious_reckless_second_half", "Cautious (Second Half)", "Reckless (Second Half)"),
]
MIN_TENDENCY = 0
MAX_TENDENCY = 100

# "W-TKO(8)": win/loss/draw, dash, method, round in parentheses. Method is
# restricted to a fixed set rather than free text so last_6 data stays
# analysable -- a typo'd method code would silently become its own
# category in any later groupby.
LAST_6_METHODS = ("KO", "TKO", "UD", "SD", "MD")
LAST_6_PATTERN = re.compile(r"^([WLD])-(" + "|".join(LAST_6_METHODS) + r")\((\d{1,2})\)$")
MAX_LAST_6_ENTRIES = 6


def validate_last_6_entry(entry: str) -> str:
    entry = (entry or "").strip()
    match = LAST_6_PATTERN.match(entry)
    if not match:
        raise FighterError(
            f'"{entry}" is not a valid last-6 result. Expected format like "W-TKO(8)" '
            f'(W/L/D, then one of {LAST_6_METHODS}, then the round in parentheses).'
        )
    round_number = int(match.group(3))
    if not (1 <= round_number <= 12):
        raise FighterError(f'"{entry}": round must be between 1 and 12.')
    return entry


def blank_meta_section(weight_limit: int = None) -> dict:
    """A fresh, blank corner meta block -- used when a fighter has no
    prior recorded meta to carry forward from. Attributes start at a
    neutral mid-scale value (5.0) and tendencies at a neutral 50 rather
    than the scale minimums, since 0.5-everywhere is a much less
    reasonable "unknown fighter" guess than "roughly average"."""
    return {
        "profile": {
            "weigh_in": weight_limit,
            "record": {"wins": 0, "knockouts": 0, "losses": 0, "draws": 0},
            "last_6": [],
        },
        "career_stats": {key: 0 for key, _ in CAREER_STAT_FIELDS},
        "attributes": {key: 5.0 for key, _ in ATTRIBUTE_FIELDS},
        "skills": {
            "experience": {"level": MIN_LEVEL, "xp": MIN_XP},
            "signature_traits": {group: None for group in SIGNATURE_TRAIT_GROUPS},
        },
        "tendencies": {key: 50 for key, _, _ in TENDENCY_FIELDS},
    }


def validate_meta_section(meta: dict, weight_limit: int, min_weigh_in: int) -> dict:
    """Validate one corner's full meta block. Returns a cleaned copy (int/
    float types normalised) or raises FighterError naming the first
    problem found. weight_limit and min_weigh_in bound the fight's
    division (see WeightClasses.get_min_weigh_in for how min_weigh_in is
    derived) -- passed in rather than looked up, since this is a pure
    data-shape check with no access to a specific fight or the weight
    classes table."""
    cleaned = {}

    # --- profile ---
    profile = meta.get("profile", {})
    try:
        weigh_in = int(profile["weigh_in"])
    except (KeyError, TypeError, ValueError):
        raise FighterError("Weigh-in is required and must be a whole number.")
    if not (min_weigh_in <= weigh_in <= weight_limit):
        raise FighterError(
            f"Weigh-in ({weigh_in} lbs) must be between {min_weigh_in} and {weight_limit} lbs "
            f"(inclusive) for this division."
        )

    record = profile.get("record", {})
    try:
        wins = int(record["wins"])
        knockouts = int(record["knockouts"])
        losses = int(record["losses"])
        draws = int(record["draws"])
    except (KeyError, TypeError, ValueError):
        raise FighterError("Record (wins/knockouts/losses/draws) must be whole numbers.")
    if min(wins, knockouts, losses, draws) < 0:
        raise FighterError("Record values cannot be negative.")
    if knockouts > wins:
        raise FighterError("Knockouts cannot exceed total wins.")

    last_6 = profile.get("last_6", [])
    if len(last_6) > MAX_LAST_6_ENTRIES:
        raise FighterError(f"last_6 holds at most {MAX_LAST_6_ENTRIES} entries.")
    last_6 = [validate_last_6_entry(entry) for entry in last_6]

    cleaned["profile"] = {
        "weigh_in": weigh_in,
        "record": {"wins": wins, "knockouts": knockouts, "losses": losses, "draws": draws},
        "last_6": last_6,
    }

    # --- career_stats ---
    stats = meta.get("career_stats", {})
    cleaned_stats = {}
    for key, label in CAREER_STAT_FIELDS:
        try:
            value = int(stats[key])
        except (KeyError, TypeError, ValueError):
            raise FighterError(f"{label} is required and must be a whole number.")
        if value < 0:
            raise FighterError(f"{label} cannot be negative.")
        cleaned_stats[key] = value
    if cleaned_stats["punches_landed"] > cleaned_stats["punches_thrown"]:
        raise FighterError("Punches Landed cannot exceed Punches Thrown.")
    cleaned["career_stats"] = cleaned_stats

    # --- attributes ---
    attrs = meta.get("attributes", {})
    cleaned_attrs = {}
    for key, label in ATTRIBUTE_FIELDS:
        try:
            value = float(attrs[key])
        except (KeyError, TypeError, ValueError):
            raise FighterError(f"{label} is required and must be a number.")
        if not (MIN_ATTRIBUTE <= value <= MAX_ATTRIBUTE):
            raise FighterError(f"{label} must be between {MIN_ATTRIBUTE} and {MAX_ATTRIBUTE}.")
        if round(value / ATTRIBUTE_STEP) != value / ATTRIBUTE_STEP:
            raise FighterError(f"{label} must be in steps of {ATTRIBUTE_STEP}.")
        cleaned_attrs[key] = value
    cleaned["attributes"] = cleaned_attrs

    # --- skills ---
    skills = meta.get("skills", {})
    experience = skills.get("experience", {})
    try:
        level = int(experience["level"])
        xp = int(experience["xp"])
    except (KeyError, TypeError, ValueError):
        raise FighterError("Experience level and XP must be whole numbers.")
    if not (MIN_LEVEL <= level <= MAX_LEVEL):
        raise FighterError(f"Experience level must be between {MIN_LEVEL} and {MAX_LEVEL}.")
    max_xp = max_xp_for_level(level)
    if not (MIN_XP <= xp <= max_xp):
        raise FighterError(f"XP at level {level} must be between {MIN_XP} and {max_xp}.")

    traits = skills.get("signature_traits", {})
    cleaned_traits = {}
    for group, options in SIGNATURE_TRAIT_GROUPS.items():
        pick = traits.get(group)
        if pick is None:
            cleaned_traits[group] = None
            continue

        try:
            trait_name = pick["name"]
            trait_level = int(pick["level"])
            trait_xp = int(pick["xp"])
        except (KeyError, TypeError, ValueError):
            raise FighterError(
                f'Signature trait for {group} must have a "name", "level", and "xp".'
            )
        if trait_name not in options:
            raise FighterError(f'"{trait_name}" is not a valid signature trait for {group}.')
        if not (MIN_TRAIT_LEVEL <= trait_level <= MAX_TRAIT_LEVEL):
            raise FighterError(
                f"{trait_name}'s level must be between {MIN_TRAIT_LEVEL} and {MAX_TRAIT_LEVEL}."
            )
        if not (MIN_TRAIT_XP <= trait_xp <= MAX_TRAIT_XP):
            raise FighterError(
                f"{trait_name}'s XP must be between {MIN_TRAIT_XP} and {MAX_TRAIT_XP}."
            )
        cleaned_traits[group] = {"name": trait_name, "level": trait_level, "xp": trait_xp}

    cleaned["skills"] = {
        "experience": {"level": level, "xp": xp},
        "signature_traits": cleaned_traits,
    }

    # --- tendencies ---
    tendencies = meta.get("tendencies", {})
    cleaned_tendencies = {}
    for key, label_a, label_b in TENDENCY_FIELDS:
        try:
            value = int(tendencies[key])
        except (KeyError, TypeError, ValueError):
            raise FighterError(f'"{label_a}/{label_b}" is required and must be a whole number.')
        if not (MIN_TENDENCY <= value <= MAX_TENDENCY):
            raise FighterError(
                f'"{label_a}/{label_b}" must be between {MIN_TENDENCY} and {MAX_TENDENCY}.'
            )
        cleaned_tendencies[key] = value
    cleaned["tendencies"] = cleaned_tendencies

    return cleaned
