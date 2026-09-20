import csv
import json
import os
import sqlite3
import sys

from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
from api.Fights import STATUS_COMPLETE

FIGHTS_CSV = os.path.join(PROJECT_ROOT, "data", "fights.csv")
FIGHTS_DIR = os.path.join(PROJECT_ROOT, "data", "fights")
WEIGHTS_CSV = os.path.join(PROJECT_ROOT, "data", "weights.csv")
FIGHTERS_CSV = os.path.join(PROJECT_ROOT, "data", "fighters.csv")

METHOD_ORDER = ["UD", "MD", "SD", "KO", "TKO"]

def load_fights_into_sqlite(conn: sqlite3.Connection) -> None:
    """CREATE TABLE + INSERT fights.csv into an in-memory SQL table."""
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
    conn.execute("CREATE TABLE fighters (FighterID INTEGER PRIMARY KEY, FirstName TEXT, LastName TEXT)")
    with open(FIGHTERS_CSV, newline="", encoding="utf-8") as f:
        rows = [(int(row["FighterID"]), row["FirstName"], row["LastName"]) for row in csv.DictReader(f)]

    conn.executemany("INSERT INTO fighters VALUES (?, ?, ?)", rows)
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
    """ Completed-fight counts per division, JOINed against weight_classes """
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
    """ Completed-fight counts per date """
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
    """ finds  most recent fight For every fighter in fighters.csv """
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
    cursor = conn.execute("SELECT FightID FROM fights WHERE Status = ?", (STATUS_COMPLETE,))
    return [row[0] for row in cursor.fetchall()]

def get_outcome_method(fight_id: str):
    path = os.path.join(FIGHTS_DIR, f"{fight_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        full = json.load(f)
    return (full.get("result") or {}).get("outcome", {}).get("method")


def outcome_method_distribution(conn: sqlite3.Connection) -> tuple:
    """Returns (method_counts: Counter, missing: int) across every completed fight """
    method_counts = Counter()
    missing = 0
    for fight_id in get_completed_fight_ids(conn):
        method = get_outcome_method(fight_id)
        if method is None:
            missing += 1
        else:
            method_counts[method] += 1
    return method_counts, missing

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
        share = f"{count / total_with_method:.1%}" if total_with_method else "--"
        print(f"  {method:<8}{count:>8}{share:>10}")

    unexpected = set(method_counts) - set(METHOD_ORDER)
    if unexpected:
        print()
        print(f"Unexpected method codes found (check data entry): {sorted(unexpected)}")

if __name__ == "__main__":
    main()