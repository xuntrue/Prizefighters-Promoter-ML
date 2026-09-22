import os
import sqlite3
import sys

from analyse_fights import (load_fights_into_sqlite, get_completed_fight_ids, load_fight_result)

def load_scored_rounds_into_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE scored_rounds (
            FightID TEXT, Judge TEXT, RoundNumber INTEGER,
            RedScore INTEGER, BlueScore INTEGER
        )
        """
    )
    rows = []
    for fight_id in get_completed_fight_ids(conn):
        scorecards = load_fight_result(fight_id).get("scorecards") or {}
        for judge, corners in scorecards.items():
            red_scores = corners.get("red_corner", [])
            blue_scores = corners.get("blue_corner", [])
            for round_number, (red_score, blue_score) in enumerate(zip(red_scores, blue_scores), start=1):
                if red_score is None or blue_score is None:
                    continue
                rows.append((fight_id, judge, round_number, int(red_score), int(blue_score)))

    conn.executemany("INSERT INTO scored_rounds VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()

def build_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    load_fights_into_sqlite(conn)
    load_scored_rounds_into_sqlite(conn)
    return conn

def count_scored_rounds(conn: sqlite3.Connection) -> int:
    """ Total (fight, judge, round) scoring instances """
    return conn.execute("SELECT COUNT(*) FROM scored_rounds").fetchone()[0]

def score_margin_distribution(conn: sqlite3.Connection) -> list:
    """ Distribution of round score pairs """
    cursor = conn.execute(
        """
        SELECT
            max(RedScore, BlueScore) || '-' || min(RedScore, BlueScore) AS ScoreLabel,
            max(RedScore, BlueScore) - min(RedScore, BlueScore) AS Margin,
            max(RedScore, BlueScore) AS HighScore,
            COUNT(*) AS RoundCount
        FROM scored_rounds
        GROUP BY ScoreLabel
        ORDER BY Margin ASC, HighScore DESC
        """
    )
    return [(label, count) for label, _margin, _high, count in cursor.fetchall()]

def red_corner_bias(conn: sqlite3.Connection) -> dict:
    """ Returns {"red_wins": int, "blue_wins": int} """
    cursor = conn.execute(
        """
        SELECT
            SUM(CASE WHEN RedScore > BlueScore THEN 1 ELSE 0 END) AS RedWins,
            SUM(CASE WHEN BlueScore > RedScore THEN 1 ELSE 0 END) AS BlueWins
        FROM scored_rounds
        WHERE RedScore != BlueScore
        """
    )
    red_wins, blue_wins = cursor.fetchone()
    red_wins = red_wins or 0
    blue_wins = blue_wins or 0
    total = red_wins + blue_wins

    return {
        "red_wins": red_wins,
        "blue_wins": blue_wins,
        "red_share": (red_wins / total) if total else 0.0,
        "blue_share": (blue_wins / total) if total else 0.0,
    }

def main():
    conn = build_connection()

    total_scored = count_scored_rounds(conn)
    print(f"Scored rounds (fight x judge x round): {total_scored}")

    if total_scored == 0:
        print("Nothing else to report yet.")
        conn.close()
        return

    print()
    print("Score margin distribution:")
    print(f"  {'Score':<10}{'Count':>8}{'Share':>10}")
    for label, count in score_margin_distribution(conn):
        share = f"{count / total_scored:.2%}"
        print(f"  {label:<10}{count:>8}{share:>10}")

    print()
    bias = red_corner_bias(conn)
    decisive = bias["red_wins"] + bias["blue_wins"]
    print(f"Red corner bias (decisive rounds only, {decisive} of {total_scored} -- ties excluded):")
    print(f"  Red corner:  {bias['red_wins']:>6}  ({bias['red_share']:.2%})")
    print(f"  Blue corner: {bias['blue_wins']:>6}  ({bias['blue_share']:.2%})")
    conn.close()

if __name__ == "__main__":
    main()