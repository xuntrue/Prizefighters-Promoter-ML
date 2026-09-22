import csv
import json
import os
import sqlite3
import sys

from collections import Counter
from itertools import combinations_with_replacement

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from api.Fights import STATUS_COMPLETE
from api.Fighter import INT_TO_STANCE, INT_TO_STYLE, STYLE_TO_INT

FIGHTS_CSV = os.path.join(PROJECT_ROOT, "data", "fights.csv")
FIGHTS_DIR = os.path.join(PROJECT_ROOT, "data", "fights")
WEIGHTS_CSV = os.path.join(PROJECT_ROOT, "data", "weights.csv")
FIGHTERS_CSV = os.path.join(PROJECT_ROOT, "data", "fighters.csv")

METHOD_ORDER = ["UD", "MD", "SD", "KO", "TKO"]

def load_fights_into_sqlite(conn: sqlite3.Connection) -> None:
    """ CREATE TABLE + INSERT fights.csv into an in-memory SQL table """
    conn.execute(
        """
        CREATE TABLE fights (
            FightID TEXT PRIMARY KEY,
            RedCornerFighterID INTEGER,
            BlueCornerFighterID INTEGER,
            WeightClass INTEGER,
            Date TEXT,
            Championship INTEGER,
            Status TEXT
        )
        """
    )

    with open(FIGHTS_CSV, newline="", encoding="utf-8") as f:
        rows = [
            (
                row["FightID"],
                int(row["RedCornerFighterID"]),
                int(row["BlueCornerFighterID"]),
                int(row["WeightClass"]),
                row["Date"],
                int(row["Championship"]),
                row["Status"],
            )
            for row in csv.DictReader(f)
        ]

    conn.executemany("INSERT INTO fights VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()

def load_weight_classes_into_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE weight_classes (
            WeightLimit INTEGER PRIMARY KEY,
            WeightClassName TEXT
        )
        """
    )
    with open(WEIGHTS_CSV, newline="", encoding="utf-8") as f:
        rows = [(int(row["weight_limit"]), row["weight_class"]) for row in csv.DictReader(f)]
    conn.executemany("INSERT INTO weight_classes VALUES (?, ?)", rows)
    conn.commit()


def load_fighters_into_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE fighters (
            FighterID INTEGER PRIMARY KEY, FirstName TEXT, LastName TEXT,
            Reach INTEGER, Stance INTEGER, Style INTEGER
        )
        """
    )
    with open(FIGHTERS_CSV, newline="", encoding="utf-8") as f:
        rows = [
            (
                int(row["FighterID"]), row["FirstName"], row["LastName"],
                int(row["Reach"]), int(row["Stance"]), int(row["Style"]),
            )
            for row in csv.DictReader(f)
        ]
    conn.executemany("INSERT INTO fighters VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.commit()

def build_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    load_fights_into_sqlite(conn)
    load_weight_classes_into_sqlite(conn)
    load_fighters_into_sqlite(conn)
    return conn

def count_completed_fights(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("SELECT COUNT(*) FROM fights WHERE Status = ?", (STATUS_COMPLETE,))
    return cursor.fetchone()[0]

def count_completed_title_fights(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "SELECT COUNT(*) FROM fights WHERE Status = ? AND Championship = 1", (STATUS_COMPLETE,)
    )
    return cursor.fetchone()[0]


def count_completed_non_title_fights(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "SELECT COUNT(*) FROM fights WHERE Status = ? AND Championship = 0", (STATUS_COMPLETE,)
    )
    return cursor.fetchone()[0]


def histogram_by_weight_class(conn: sqlite3.Connection) -> list:
    """Completed-fight counts per division, JOINed against weight_classes
    so the report shows a name, not just a bare weight limit. Returns a
    list of (weight_limit, weight_class_name, count) ordered lightest to
    heaviest."""
    cursor = conn.execute(
        """
        SELECT f.WeightClass, w.WeightClassName, COUNT(*) AS FightCount
        FROM fights AS f
        JOIN weight_classes AS w ON w.WeightLimit = f.WeightClass
        WHERE f.Status = ?
        GROUP BY f.WeightClass
        ORDER BY f.WeightClass ASC
        """,
        (STATUS_COMPLETE,),
    )
    return cursor.fetchall()


def histogram_by_date(conn: sqlite3.Connection) -> list:
    """Completed-fight counts per date. Date is stored as "dd-mm-yyyy"
    text, which sorts WRONG chronologically as a plain string (e.g.
    "05-02-2026" would sort before "12-01-2026", even though January
    comes first) -- so ORDER BY rearranges each value into "yyyy-mm-dd"
    with substr() before sorting, without needing to touch the data
    itself. Returns a list of (date_str, count)."""
    cursor = conn.execute(
        """
        SELECT Date, COUNT(*) AS FightCount
        FROM fights
        WHERE Status = ?
        GROUP BY Date
        ORDER BY substr(Date, 7, 4) || '-' || substr(Date, 4, 2) || '-' || substr(Date, 1, 2)
        """,
        (STATUS_COMPLETE,),
    )
    return cursor.fetchall()


def fighter_appearance_frequency(conn: sqlite3.Connection) -> list:
    """How many completed fights each fighter appears in, counting both
    corners. ("frequency of FighterID recorded" in either corner --
    read as FighterID rather than FightID, since a fight only has one
    ID and "either the red or blue corner" only makes sense for a
    fighter. Flag if that's not what was meant.)

    UNION ALL stacks the red-corner and blue-corner ID columns into one
    column before grouping -- the standard way to count something that's
    spread across two columns instead of one row per occurrence."""
    cursor = conn.execute(
        """
        SELECT FighterID, COUNT(*) AS Fights
        FROM (
            SELECT RedCornerFighterID AS FighterID FROM fights WHERE Status = ?
            UNION ALL
            SELECT BlueCornerFighterID AS FighterID FROM fights WHERE Status = ?
        )
        GROUP BY FighterID
        ORDER BY Fights DESC, FighterID ASC
        """,
        (STATUS_COMPLETE, STATUS_COMPLETE),
    )
    return cursor.fetchall()


VALID_SORTS = (None, "asc", "desc")


def last_fight_per_fighter(conn: sqlite3.Connection, sort: str = None) -> list:
    """
    For every fighter in fighters.csv, finds their most recent fight in
    fights.csv BY DATE -- regardless of that fight's Status, so a
    Cancelled or still-Scheduled fight counts the same as a Complete one
    here. A fighter who's never been scheduled for anything gets a null
    fight/date rather than being left out.

    Uses a window function (ROW_NUMBER() OVER (PARTITION BY ...)) rather
    than a correlated subquery -- the standard modern-SQL way to solve
    "one row per group, ranked by something" (the "greatest-n-per-group"
    problem), and one of the more commonly-asked SQL interview patterns.

    sort controls the row order:
        None   -> FighterID ascending (the default)
        "asc"  -> fighters with no recorded fight first, then by their
                  last fight's date, oldest first
        "desc" -> the exact reverse: most recent last-fight date first,
                  fighters with no recorded fight last

    The None-first/None-last placement comes for free from SQLite's own
    rule that NULL sorts as smaller than any real value (so NULLs land
    first under ASC, last under DESC) -- confirmed by direct testing
    below rather than just trusted from the docs, since a wrong
    assumption about null ordering is exactly the kind of thing that's
    easy to ship unnoticed.

    sort is validated against a fixed whitelist and only ever used to
    pick one of three hardcoded ORDER BY clauses -- never spliced into
    the query from the argument directly -- since column/direction
    names can't go through a `?` placeholder the way values can.
    """
    if sort not in VALID_SORTS:
        raise ValueError(f"sort must be one of {VALID_SORTS}, got {sort!r}")

    order_clause = {
        None: "f.FighterID ASC",
        "asc": "SortDate ASC",
        "desc": "SortDate DESC",
    }[sort]

    cursor = conn.execute(
        f"""
        WITH fighter_fights AS (
            SELECT RedCornerFighterID AS FighterID, FightID, Date,
                   substr(Date, 7, 4) || '-' || substr(Date, 4, 2) || '-' || substr(Date, 1, 2) AS SortDate
            FROM fights
            UNION ALL
            SELECT BlueCornerFighterID AS FighterID, FightID, Date,
                   substr(Date, 7, 4) || '-' || substr(Date, 4, 2) || '-' || substr(Date, 1, 2) AS SortDate
            FROM fights
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY FighterID ORDER BY SortDate DESC) AS rn
            FROM fighter_fights
        )
        SELECT f.FighterID, f.FirstName || ' ' || f.LastName AS FighterName,
               r.FightID, r.Date
        FROM fighters AS f
        LEFT JOIN ranked AS r ON r.FighterID = f.FighterID AND r.rn = 1
        ORDER BY {order_clause}
        """
    )
    return cursor.fetchall()


def get_completed_fight_ids(conn: sqlite3.Connection) -> list:
    """Every FightID whose Status is Complete -- used to look up each
    fight's outcome method, which isn't a column in fights.csv."""
    cursor = conn.execute("SELECT FightID FROM fights WHERE Status = ?", (STATUS_COMPLETE,))
    return [row[0] for row in cursor.fetchall()]


def load_fight_json(fight_id: str):
    """The full parsed JSON for one fight, or None if the file is missing."""
    path = os.path.join(FIGHTS_DIR, f"{fight_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_fight_result(fight_id: str) -> dict:
    """The "result" object from a fight's JSON, or {} if missing."""
    full = load_fight_json(fight_id)
    return (full or {}).get("result") or {}


def load_fight_meta(fight_id: str) -> dict:
    """The "meta" object from a fight's JSON, or {} if missing."""
    full = load_fight_json(fight_id)
    return (full or {}).get("meta") or {}


def get_outcome_method(fight_id: str):
    """The outcome method isn't in fights.csv -- pull it from the
    fight's own JSON file."""
    return load_fight_result(fight_id).get("outcome", {}).get("method")


def outcome_method_distribution(conn: sqlite3.Connection) -> tuple:
    """Returns (method_counts: Counter, missing: int) across every
    completed fight, read from each fight's own JSON file."""
    method_counts = Counter()
    missing = 0
    for fight_id in get_completed_fight_ids(conn):
        method = get_outcome_method(fight_id)
        if method is None:
            missing += 1
        else:
            method_counts[method] += 1
    return method_counts, missing


# ==================== Matchup combination tables ====================

def _matchup_key(label_a: str, label_b: str, canonical_order: list) -> str:
    """Order-independent matchup label, e.g. "Orthodox vs. Southpaw" --
    always listed in canonical_order regardless of which label came from
    the red corner vs. the blue corner, so "Orthodox vs. Southpaw" and
    "Southpaw vs. Orthodox" collapse into the same key. Falls back to
    sorting an unrecognised label after all known ones rather than
    raising, since this reads fighters.csv/JSON data that could in
    principle have been hand-edited into something unexpected."""
    index = {label: i for i, label in enumerate(canonical_order)}
    a, b = sorted([label_a, label_b], key=lambda label: index.get(label, len(canonical_order)))
    return f"{a} vs. {b}"


def _all_matchup_keys(canonical_order: list) -> list:
    """Every possible unordered pairing, INCLUDING a category against
    itself, in canonical order -- e.g. for [Orthodox, Southpaw]:
    Orthodox vs. Orthodox, Orthodox vs. Southpaw, Southpaw vs. Southpaw.
    Used to pre-seed a distribution with every combination at 0, so the
    printed table is complete even for combinations that never occurred,
    not just whatever happened to show up in the data."""
    return [f"{a} vs. {b}" for a, b in combinations_with_replacement(canonical_order, 2)]


STANCE_ORDER = [INT_TO_STANCE[0], INT_TO_STANCE[1]]  # ["Orthodox", "Southpaw"]
STYLE_ORDER = [INT_TO_STYLE[i] for i in range(1, len(STYLE_TO_INT) + 1)]  # canonical 1..4 order
GYM_ORDER = ["Gym", "Free Agent"]


def stance_matchup_distribution(conn: sqlite3.Connection) -> dict:
    """Every completed fight's stance pairing (Orthodox/Southpaw, a
    fixed fighter attribute from fighters.csv), collapsed into the 3
    possible unordered combinations. Pure SQL -- no JSON needed, since
    stance doesn't vary fight to fight."""
    counts = {key: 0 for key in _all_matchup_keys(STANCE_ORDER)}
    cursor = conn.execute(
        """
        SELECT rf.Stance, bf.Stance
        FROM fights AS fi
        JOIN fighters AS rf ON rf.FighterID = fi.RedCornerFighterID
        JOIN fighters AS bf ON bf.FighterID = fi.BlueCornerFighterID
        WHERE fi.Status = ?
        """,
        (STATUS_COMPLETE,),
    )
    for red_stance, blue_stance in cursor.fetchall():
        red_label = INT_TO_STANCE.get(red_stance, f"Unknown({red_stance})")
        blue_label = INT_TO_STANCE.get(blue_stance, f"Unknown({blue_stance})")
        key = _matchup_key(red_label, blue_label, STANCE_ORDER)
        counts[key] = counts.get(key, 0) + 1
    return counts


def style_matchup_distribution(conn: sqlite3.Connection) -> dict:
    """Same idea as stance, but for the 4 fighting styles -- 10 possible
    unordered combinations (4 same-style + 6 cross-style)."""
    counts = {key: 0 for key in _all_matchup_keys(STYLE_ORDER)}
    cursor = conn.execute(
        """
        SELECT rf.Style, bf.Style
        FROM fights AS fi
        JOIN fighters AS rf ON rf.FighterID = fi.RedCornerFighterID
        JOIN fighters AS bf ON bf.FighterID = fi.BlueCornerFighterID
        WHERE fi.Status = ?
        """,
        (STATUS_COMPLETE,),
    )
    for red_style, blue_style in cursor.fetchall():
        red_label = INT_TO_STYLE.get(red_style, f"Unknown({red_style})")
        blue_label = INT_TO_STYLE.get(blue_style, f"Unknown({blue_style})")
        key = _matchup_key(red_label, blue_label, STYLE_ORDER)
        counts[key] = counts.get(key, 0) + 1
    return counts


def gym_matchup_distribution(conn: sqlite3.Connection) -> dict:
    """Whether each corner had a cornering gym at all, not whether it
    was literally the SAME gym for both fighters. This is fight-specific
    (a fighter can be a free agent for one fight and gym-affiliated for
    the next), so unlike stance/style it has to come from each fight's
    own JSON (result.gyms), not a fixed fighters.csv column."""
    counts = {key: 0 for key in _all_matchup_keys(GYM_ORDER)}
    for fight_id in get_completed_fight_ids(conn):
        gyms = load_fight_result(fight_id).get("gyms")
        if not gyms:
            continue
        red_label = "Gym" if gyms.get("red_corner") is not None else "Free Agent"
        blue_label = "Gym" if gyms.get("blue_corner") is not None else "Free Agent"
        key = _matchup_key(red_label, blue_label, GYM_ORDER)
        counts[key] = counts.get(key, 0) + 1
    return counts


def corner_win_distribution(conn: sqlite3.Connection) -> dict:
    """Red corner wins vs. Blue corner wins vs. Draws. Needs each
    fight's JSON for outcome.winner_id (not in fights.csv), compared
    against fights.csv's own corner assignments to know which corner
    that winner was actually sitting in -- winner_id is a FighterID, not
    a corner label."""
    counts = {"Red corner win": 0, "Blue corner win": 0, "Draw": 0}
    cursor = conn.execute(
        "SELECT FightID, RedCornerFighterID, BlueCornerFighterID FROM fights WHERE Status = ?",
        (STATUS_COMPLETE,),
    )
    for fight_id, red_id, blue_id in cursor.fetchall():
        winner_id = load_fight_result(fight_id).get("outcome", {}).get("winner_id")
        if winner_id is None:
            counts["Draw"] += 1
        elif winner_id == red_id:
            counts["Red corner win"] += 1
        elif winner_id == blue_id:
            counts["Blue corner win"] += 1
        else:
            counts[f"Unexpected winner_id {winner_id} (data issue, fight {fight_id})"] = 1
    return counts


# =================== Weight/reach difference histograms ===================

def _bucket(value: int, bucket_size: int) -> str:
    start = (value // bucket_size) * bucket_size
    return f"{start}-{start + bucket_size - 1}"


def weight_difference_histogram(conn: sqlite3.Connection, bucket_size: int = 1) -> list:
    """
    Distribution of |red weigh-in - blue weigh-in|, in pounds.

    Both fighters in a fight are always registered to the SAME division
    (enforced at scheduling time), so this is never a difference in
    weight CLASS -- it's the actual weigh-in each fighter posted on the
    day, which is free to vary within the division's own allowed range.
    That value lives in each fight's pre-fight meta (profile.weigh_in),
    not fighters.csv (which has no weigh-in column) or fights.csv
    (which only records the division, not a specific weight) -- so this
    one needs each fight's JSON, unlike reach_difference_histogram below.

    Bucketed in Python rather than SQL, since the values themselves only
    exist after parsing JSON -- there's no SQL table to GROUP BY here.
    """
    bucket_size = int(bucket_size)
    if bucket_size <= 0:
        raise ValueError(f"bucket_size must be a positive integer, got {bucket_size}")

    counts = Counter()
    for fight_id in get_completed_fight_ids(conn):
        meta = load_fight_meta(fight_id)
        red_weigh_in = (meta.get("red_corner") or {}).get("profile", {}).get("weigh_in")
        blue_weigh_in = (meta.get("blue_corner") or {}).get("profile", {}).get("weigh_in")
        if red_weigh_in is None or blue_weigh_in is None:
            continue
        counts[_bucket(abs(red_weigh_in - blue_weigh_in), bucket_size)] += 1

    return sorted(counts.items(), key=lambda row: int(row[0].split("-")[0]))


def reach_difference_histogram(conn: sqlite3.Connection, bucket_size: int = 1) -> list:
    """
    Distribution of |red reach - blue reach|, in inches, from
    fighters.csv -- a fixed physical attribute, unlike weigh-in above,
    so this one stays entirely in SQL. bucket_size is passed through a
    real `?` placeholder (twice -- once for the division, once for the
    multiplication) rather than interpolated into the query text, since
    it's genuinely just a value here, not a column or direction name --
    those are the only things `?` placeholders can't stand in for.
    """
    bucket_size = int(bucket_size)
    if bucket_size <= 0:
        raise ValueError(f"bucket_size must be a positive integer, got {bucket_size}")

    cursor = conn.execute(
        """
        SELECT (ABS(rf.Reach - bf.Reach) / ?) * ? AS BucketStart, COUNT(*) AS FighterCount
        FROM fights AS fi
        JOIN fighters AS rf ON rf.FighterID = fi.RedCornerFighterID
        JOIN fighters AS bf ON bf.FighterID = fi.BlueCornerFighterID
        WHERE fi.Status = ?
        GROUP BY BucketStart
        ORDER BY BucketStart
        """,
        (bucket_size, bucket_size, STATUS_COMPLETE),
    )
    return [(f"{start}-{start + bucket_size - 1}", count) for start, count in cursor.fetchall()]


# ============================= Printing =============================

def main():
    conn = build_connection()

    total_completed = count_completed_fights(conn)
    print(f"Completed fights: {total_completed}")

    if total_completed == 0:
        print("Nothing else to report yet.")
        conn.close()
        return

    title_count = count_completed_title_fights(conn)
    non_title_count = count_completed_non_title_fights(conn)
    print(f"  Title fights:     {title_count}")
    print(f"  Non-title fights: {non_title_count}")

    print()
    print("Completed fights by weight class:")
    print(f"  {'Weight Class':<20}{'Limit':>8}{'Count':>8}")
    for weight_limit, weight_class_name, count in histogram_by_weight_class(conn):
        print(f"  {weight_class_name:<20}{weight_limit:>8}{count:>8}")

    print()
    print("Completed fights by date:")
    print(f"  {'Date':<12}{'Count':>8}")
    for date_str, count in histogram_by_date(conn):
        print(f"  {date_str:<12}{count:>8}")

    print()
    print("Fighter appearance frequency (completed fights, either corner):")
    print(f"  {'FighterID':<12}{'Fights':>8}")
    for fighter_id, count in fighter_appearance_frequency(conn):
        print(f"  {fighter_id:<12}{count:>8}")

    print()
    print("Last recorded fight per fighter (any status, sort='asc'):")
    print(f"  {'FighterID':<10}{'Name':<22}{'FightID':<10}{'Date':<12}")
    for fighter_id, name, fight_id, fight_date in last_fight_per_fighter(conn, sort="asc"):
        print(f"  {fighter_id:<10}{name:<22}{fight_id or '--':<10}{fight_date or 'No last fight':<12}")

    print()
    print("Stance matchups (pure SQL, no JSON needed):")
    for label, count in stance_matchup_distribution(conn).items():
        print(f"  {label:<28}{count:>6}")

    print()
    print("Style matchups (pure SQL, no JSON needed):")
    for label, count in style_matchup_distribution(conn).items():
        print(f"  {label:<32}{count:>6}")

    print()
    print("Gym matchups (from each fight's JSON):")
    for label, count in gym_matchup_distribution(conn).items():
        print(f"  {label:<28}{count:>6}")

    print()
    print("Corner win distribution (from each fight's JSON):")
    for label, count in corner_win_distribution(conn).items():
        print(f"  {label:<28}{count:>6}")

    print()
    print("Weigh-in difference (lbs, from each fight's JSON):")
    for label, count in weight_difference_histogram(conn):
        print(f"  {label:<10}{count:>6}")

    print()
    print("Reach difference (inches, from fighters.csv):")
    for label, count in reach_difference_histogram(conn):
        print(f"  {label:<10}{count:>6}")

    method_counts, missing = outcome_method_distribution(conn)
    conn.close()

    total_with_method = sum(method_counts.values())
    print()
    print(f"Outcome method distribution:")
    if missing:
        print(f"  ({missing} completed fight(s) had no recorded outcome method and were skipped)")
    print(f"  {'Method':<8}{'Count':>8}{'Share':>10}")
    print("  " + "-" * 24)
    for method in METHOD_ORDER:
        count = method_counts.get(method, 0)
        share = f"{count / total_with_method:.2%}" if total_with_method else "--"
        print(f"  {method:<8}{count:>8}{share:>10}")

    unexpected = set(method_counts) - set(METHOD_ORDER)
    if unexpected:
        print()
        print(f"Unexpected method codes found (check data entry): {sorted(unexpected)}")


if __name__ == "__main__":
    main()
