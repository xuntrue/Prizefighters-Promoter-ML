"""
analyse_fighters.py

Distributions and cross-cuts across the fighter roster, joining
fighters.csv, countries.csv, records.csv, and (for division names)
weights.csv.

Same discipline as analyse_fights.py: every function takes an open
sqlite3 connection and returns data -- nothing prints except main().
Enum-style columns (Stance, Style) are translated to labels in Python
using the SAME dicts the app itself uses (api.Fighter.INT_TO_STANCE /
INT_TO_STYLE), rather than duplicating "0 = Orthodox" as a second,
driftable copy inside a SQL CASE WHEN. Everything else -- the actual
joins, grouping, filtering, aggregation -- is real SQL.

Run from anywhere:
    python analysis/analyse_fighters.py
"""

import csv
import os
import sqlite3
import sys
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)  # so `from api...` works when run directly

from api.Fighter import INT_TO_STANCE, INT_TO_STYLE  # noqa: E402

FIGHTERS_CSV = os.path.join(PROJECT_ROOT, "data", "fighters.csv")
COUNTRIES_CSV = os.path.join(PROJECT_ROOT, "data", "countries.csv")
RECORDS_CSV = os.path.join(PROJECT_ROOT, "data", "records.csv")
WEIGHTS_CSV = os.path.join(PROJECT_ROOT, "data", "weights.csv")


# ============================= Loading =============================

def load_fighters(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE fighters (
            FighterID INTEGER PRIMARY KEY,
            FirstName TEXT, LastName TEXT, Nickname TEXT, Placement TEXT,
            Hometown TEXT, Country TEXT, Birthdate TEXT,
            Weightclass INTEGER, Reach INTEGER, Stance INTEGER, Style INTEGER
        )
        """
    )
    with open(FIGHTERS_CSV, newline="", encoding="utf-8") as f:
        rows = [
            (
                int(r["FighterID"]), r["FirstName"], r["LastName"], r["Nickname"], r["Placement"],
                r["Hometown"], r["Country"], r["Birthdate"],
                int(r["Weightclass"]), int(r["Reach"]), int(r["Stance"]), int(r["Style"]),
            )
            for r in csv.DictReader(f)
        ]
    conn.executemany("INSERT INTO fighters VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()


def load_countries(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE countries (A2 TEXT PRIMARY KEY, CountryName TEXT)")
    with open(COUNTRIES_CSV, newline="", encoding="utf-8") as f:
        rows = [(r["A-2"], r["CountryName"]) for r in csv.DictReader(f)]
    conn.executemany("INSERT INTO countries VALUES (?, ?)", rows)
    conn.commit()


def load_records(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE records (FighterID INTEGER PRIMARY KEY, Wins INTEGER, "
        "Knockouts INTEGER, Losses INTEGER, Draws INTEGER)"
    )
    with open(RECORDS_CSV, newline="", encoding="utf-8") as f:
        rows = [
            (int(r["FighterID"]), int(r["Wins"]), int(r["Knockouts"]), int(r["Losses"]), int(r["Draws"]))
            for r in csv.DictReader(f)
        ]
    conn.executemany("INSERT INTO records VALUES (?,?,?,?,?)", rows)
    conn.commit()


def load_weight_classes(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE weight_classes (WeightLimit INTEGER PRIMARY KEY, WeightClassName TEXT)")
    with open(WEIGHTS_CSV, newline="", encoding="utf-8") as f:
        rows = [(int(r["weight_limit"]), r["weight_class"]) for r in csv.DictReader(f)]
    conn.executemany("INSERT INTO weight_classes VALUES (?, ?)", rows)
    conn.commit()


def build_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    load_fighters(conn)
    load_countries(conn)
    load_records(conn)
    load_weight_classes(conn)
    return conn


# ============================= Queries =============================

def count_total_fighters(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM fighters").fetchone()[0]


def fighters_by_country(conn: sqlite3.Connection) -> list:
    """Roster size per country, busiest first.

    LEFT JOIN rather than a plain JOIN, deliberately: the app itself
    validates every fighter's Country against countries.csv at write
    time, so an orphaned code shouldn't happen through normal use -- but
    this script reads the CSVs directly, and CSVs get hand-edited. An
    INNER JOIN would silently drop any fighter whose country code had no
    match, quietly under-reporting the roster; COALESCE surfaces it as
    an "Unknown" line instead."""
    cursor = conn.execute(
        """
        SELECT COALESCE(c.CountryName, 'Unknown (' || f.Country || ')') AS CountryLabel,
               COUNT(*) AS FighterCount
        FROM fighters AS f
        LEFT JOIN countries AS c ON c.A2 = f.Country
        GROUP BY CountryLabel
        ORDER BY FighterCount DESC, CountryLabel ASC
        """
    )
    return cursor.fetchall()


def fighters_by_weight_class(conn: sqlite3.Connection) -> list:
    """Roster size per division, lightest to heaviest."""
    cursor = conn.execute(
        """
        SELECT w.WeightLimit, w.WeightClassName, COUNT(*) AS FighterCount
        FROM fighters AS f
        JOIN weight_classes AS w ON w.WeightLimit = f.Weightclass
        GROUP BY w.WeightLimit
        ORDER BY w.WeightLimit ASC
        """
    )
    return cursor.fetchall()


def stance_distribution(conn: sqlite3.Connection) -> dict:
    """{stance_label: count}. Stance is an int in the data (0/1) -- the
    label comes from api.Fighter.INT_TO_STANCE, not a duplicated SQL
    CASE WHEN, so this can't drift out of sync with the app itself."""
    cursor = conn.execute("SELECT Stance, COUNT(*) FROM fighters GROUP BY Stance")
    return {INT_TO_STANCE.get(stance, f"Unknown({stance})"): count for stance, count in cursor.fetchall()}


def style_distribution(conn: sqlite3.Connection) -> dict:
    cursor = conn.execute("SELECT Style, COUNT(*) FROM fighters GROUP BY Style")
    return {INT_TO_STYLE.get(style, f"Unknown({style})"): count for style, count in cursor.fetchall()}


def average_reach_by_weight_class(conn: sqlite3.Connection) -> list:
    """Does reach scale with weight class, the way you'd expect? AVG()
    plus a JOIN for the division name, ROUNDed to one decimal."""
    cursor = conn.execute(
        """
        SELECT w.WeightLimit, w.WeightClassName, ROUND(AVG(f.Reach), 1) AS AvgReach, COUNT(*) AS FighterCount
        FROM fighters AS f
        JOIN weight_classes AS w ON w.WeightLimit = f.Weightclass
        GROUP BY w.WeightLimit
        ORDER BY w.WeightLimit ASC
        """
    )
    return cursor.fetchall()


def record_totals_by_country(conn: sqlite3.Connection, min_fighters: int = 1) -> list:
    """A real three-table JOIN: fighters -> records -> countries.
    SUMs wins/losses/KOs per country and computes each country's overall
    KO rate among its wins. HAVING filters out countries with too few
    fighters to mean anything, the way min_fighters=1 (the default)
    trivially doesn't, but min_fighters=5 would."""
    cursor = conn.execute(
        """
        SELECT
            COALESCE(c.CountryName, 'Unknown (' || f.Country || ')') AS CountryLabel,
            COUNT(*) AS FighterCount,
            SUM(r.Wins) AS TotalWins,
            SUM(r.Losses) AS TotalLosses,
            SUM(r.Knockouts) AS TotalKnockouts,
            ROUND(100.0 * SUM(r.Knockouts) / NULLIF(SUM(r.Wins), 0), 1) AS KoRatePct
        FROM fighters AS f
        JOIN records AS r ON r.FighterID = f.FighterID
        LEFT JOIN countries AS c ON c.A2 = f.Country
        GROUP BY CountryLabel
        HAVING COUNT(*) >= ?
        ORDER BY TotalWins DESC
        """,
        (min_fighters,),
    )
    return cursor.fetchall()


def top_ko_artists(conn: sqlite3.Connection, min_wins: int = 5, limit: int = 10) -> list:
    """Highest KO-rate fighters, restricted to those with at least
    min_wins wins -- without the HAVING clause, a 1-0 fighter whose only
    win was a KO would show a meaningless 100% and crowd out fighters
    with real sample sizes."""
    cursor = conn.execute(
        """
        SELECT
            f.FirstName || ' ' || f.LastName AS FighterName,
            r.Wins, r.Knockouts,
            ROUND(100.0 * r.Knockouts / r.Wins, 1) AS KoRatePct
        FROM fighters AS f
        JOIN records AS r ON r.FighterID = f.FighterID
        WHERE r.Wins >= ?
        GROUP BY f.FighterID
        HAVING r.Wins >= ?
        ORDER BY KoRatePct DESC, r.Wins DESC
        LIMIT ?
        """,
        (min_wins, min_wins, limit),
    )
    return cursor.fetchall()


def undefeated_fighters(conn: sqlite3.Connection) -> list:
    """Fighters with at least one win and never a loss or a draw."""
    cursor = conn.execute(
        """
        SELECT f.FirstName || ' ' || f.LastName AS FighterName,
               COALESCE(c.CountryName, 'Unknown (' || f.Country || ')') AS CountryLabel,
               r.Wins, r.Knockouts
        FROM fighters AS f
        JOIN records AS r ON r.FighterID = f.FighterID
        LEFT JOIN countries AS c ON c.A2 = f.Country
        WHERE r.Wins > 0 AND r.Losses = 0 AND r.Draws = 0
        ORDER BY r.Wins DESC
        """
    )
    return cursor.fetchall()


def nickname_coverage(conn: sqlite3.Connection) -> tuple:
    """(fighters_with_a_nickname, total_fighters). TRIM() + a CASE WHEN
    treats whitespace-only nicknames the same as truly empty ones."""
    cursor = conn.execute(
        """
        SELECT
            SUM(CASE WHEN TRIM(Nickname) != '' THEN 1 ELSE 0 END) AS WithNickname,
            COUNT(*) AS Total
        FROM fighters
        """
    )
    return cursor.fetchone()


def age_bucket_histogram(conn: sqlite3.Connection, as_of: str = None, bucket_size: int = 5) -> list:
    bucket_size = int(bucket_size)
    if bucket_size <= 0:
        raise ValueError(f"bucket_size must be a positive integer, got {bucket_size}")

    if as_of is None:
        as_of_sql = "julianday('now')"
        params = ()
    else:
        as_of_sql = "julianday(substr(?,7,4) || '-' || substr(?,4,2) || '-' || substr(?,1,2))"
        params = (as_of, as_of, as_of)

    cursor = conn.execute(
        f"""
        SELECT
            (Age / {bucket_size}) * {bucket_size} AS BucketStart,
            COUNT(*) AS FighterCount
        FROM (
            SELECT
                CAST(
                    ({as_of_sql} - julianday(substr(Birthdate,7,4) || '-' || substr(Birthdate,4,2)
                                              || '-' || substr(Birthdate,1,2))) / 365.25
                AS INTEGER) AS Age
            FROM fighters
        )
        GROUP BY BucketStart
        ORDER BY BucketStart
        """,
        params,
    )
    return [(f"{start}-{start + bucket_size - 1}", count) for start, count in cursor.fetchall()]


def find_invalid_birthdates(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        """
        SELECT
            FighterID,
            FirstName,
            LastName,
            Birthdate
        FROM fighters
        WHERE
            Birthdate IS NULL
            OR julianday(
                substr(Birthdate, 7, 4) || '-' ||
                substr(Birthdate, 4, 2) || '-' ||
                substr(Birthdate, 1, 2)
            ) IS NULL
        ORDER BY FighterID
        """
    ).fetchall()
    return rows

# ============================= Printing =============================
def main():
    conn = build_connection()

    total = count_total_fighters(conn)
    print(f"Total fighters: {total}")
    if total == 0:
        print("Nothing else to report yet.")
        conn.close()
        return

    print()
    print("Fighters by country:")
    for country, count in fighters_by_country(conn):
        print(f"  {country:<25}{count:>6}")

    print()
    print("Fighters by weight class:")
    for _limit, name, count in fighters_by_weight_class(conn):
        print(f"  {name:<20}{count:>6}")

    print()
    print("Stance distribution:")
    for label, count in stance_distribution(conn).items():
        print(f"  {label:<12}{count:>6}")

    print()
    print("Style distribution:")
    for label, count in style_distribution(conn).items():
        print(f"  {label:<15}{count:>6}")

    print()
    print("Average reach by weight class:")
    for _limit, name, avg_reach, count in average_reach_by_weight_class(conn):
        print(f"  {name:<20}{avg_reach:>6}\"  (n={count})")

    print()
    print("Record totals by country:")
    print(f"  {'Country':<25}{'Fighters':>9}{'Wins':>7}{'Losses':>8}{'KO Rate':>9}")
    for country, n, wins, losses, kos, ko_rate in record_totals_by_country(conn):
        ko_rate_str = f"{ko_rate}%" if ko_rate is not None else "--"
        print(f"  {country:<25}{n:>9}{wins:>7}{losses:>8}{ko_rate_str:>9}")

    print()
    print("Top KO artists (min 5 wins):")
    for name, wins, kos, ko_rate in top_ko_artists(conn):
        print(f"  {name:<25}{wins:>3}W  {kos:>3}KO  {ko_rate:>5}%")

    print()
    undefeated = undefeated_fighters(conn)
    print(f"Undefeated fighters: {len(undefeated)}")
    for name, country, wins, kos in undefeated:
        print(f"  {name:<25}{country:<25}{wins}-0-0 ({kos} KO)")

    print()
    with_nick, total_fighters = nickname_coverage(conn)
    print(f"Nickname coverage: {with_nick}/{total_fighters} ({with_nick / total_fighters:.1%})")

    print()
    print("Age distribution")
    invalid = find_invalid_birthdates(conn)
    for fighter_id, first_name, last_name, birthdate in invalid:
        print(
            f"Invalid birthdate: "
            f"{fighter_id} - {first_name} {last_name}: {birthdate!r}"
        )
    for bucket, count in age_bucket_histogram(conn, as_of='01-01-2000', bucket_size=5):
        print(f"  {bucket:<10}{count:>6}")

    conn.close()


if __name__ == "__main__":
    main()
