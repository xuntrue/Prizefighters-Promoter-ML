# Prizefighters Promoter ML

A data-tracking companion app for **Prizefighters 2** (Koality Studios), built around its **"Be the Promoter"** game mode. The app is a Python/tkinter desktop tool for logging everything a fictional boxing promotion generates — fighters, fights, events, monthly rankings, pre-fight scouting reports, and full round-by-round fight results — into a structured, analysis-ready dataset. A second layer of scripts then mines that dataset with SQL, and a planned third layer will train ML models on top of it.

This project exists as a portfolio piece: a way to practice the layered application design, data modeling, SQL, and data-analysis skills relevant to data analyst / data engineering work, using a real (if playful) dataset that grows every time the game is played.

## Why this exists

Prizefighters 2 generates rich promotion data in-session — fighter attributes, monthly rankings, event cards, judges' scorecards — but doesn't expose any of it for external analysis. This project captures that data by hand, as it's produced during play, in a form suited to later analysis:

1. **Track** — a tkinter app mirrors the promoter's workflow (sign fighters, schedule fights, build events, record pre-fight scouting reports, log full results) and writes everything to disk in a consistent, validated schema.
2. **Analyze** — a set of standalone scripts load that data into an in-memory SQLite database and answer real questions about it with SQL: outcome distributions, roster demographics, judge-scoring bias, and more.
3. **Predict** *(planned)* — with enough recorded fights, train models to predict match outcomes, judge scoring, and P4P ranking movement.

## Features

The app is organized as a tabbed notebook, one tab per workflow:

| Tab | Purpose |
|---|---|
| **Add Fighter** | Register a new fighter (bio, physical attributes, stance/style, weigh-in record) with a live preview of their full ring name, country flag, and age. |
| **Edit Fighter** | Search fighters by name and update their profile. |
| **Rankings** | Record monthly divisional, pound-for-pound, and fan-favourite rankings. A month/division selector shows only months that actually exist (plus the next open slot), carries forward the previous month's roster, and flags each fighter's rank movement since the last recorded snapshot. |
| **Schedule Fight** | Book a bout: date, division, red/blue corners, rounds, and title status. |
| **Create Event** | Assemble scheduled bouts on the same date into a card — main event, co-mains, and undercard — under a headliner, arena, and slogan. |
| **Pre-Fight Meta** | Log each fighter's scouting report the day before a fight: weigh-in, record, recent form, career stats, physical attributes, skills, and stylistic tendencies. |
| **Record Result** | Log the full outcome the day of the fight: cornering gyms, round-by-round punch stats, all three judges' scorecards, the stoppage (if any), the official outcome, and each fighter's post-fight changes. |
| **Settings** | Manage reference data: weight classes, arenas, gyms, and (read-only) countries. |

## Architecture

```
ui/       tkinter screens -- one per tab, plus a couple of shared widgets
api/      PrizefighterAPI, a facade the UI talks to exclusively
data/     the actual dataset (CSV + JSON)
analysis/ standalone SQL/analysis scripts, run independently of the app
```

The UI never touches files under `data/` directly — every read and write goes through **`PrizefighterAPI`**, a facade over a set of per-entity modules (`Fighter`, `Records`, `Fights`, `Events`, `Rankings`, `Arenas`, `Gyms`, `Country`, `Weight_Classes`). Each module owns one part of the schema, validates its own data, and the facade coordinates anything that spans more than one — creating a fighter's zeroed-out record alongside their profile, flipping a fight's status once both corners' pre-fight reports are in, correcting a fighter's record when a result is saved.

## Data model

- **`fighters.csv` / `records.csv`** — one row per fighter / one row per current record, kept separate so a fighter's biographical data and in-ring record can change independently.
- **`weights.csv`, `arenas.csv`, `gyms.csv`, `countries.csv`** — reference data.
- **`fights.csv` + `data/fights/<FightID>.json`** — a fight's essential fields (corners, division, date, title status, status) live in the CSV as a fast, searchable index; everything else (sanctioned rounds, pre-fight scouting `meta`, and the post-fight `result` — punch stats, scorecards, stoppage, outcome, post-fight changes) lives in that fight's own JSON file. `FightID` is a 6-digit hex string mapping directly to its file.
- **`events.json`** — event cards (main event, co-mains, undercard, arena, headliner), a single JSON array since the roster of bouts per card is small and variable-length.
- **`rankings/rankings.csv`, `rankings/fan_rankings.csv`** — monthly snapshots in long format (one row per ranked fighter per month), including the division a fighter competed in *at the time* — not their current one — since fighters move between divisions over a career.

Every write is validated: foreign keys are checked against the relevant reference data, numeric ranges and formats are enforced (weigh-ins against a division's actual bounds, scorecards against the 10-point system, punch counts where landed can't exceed thrown), and cross-file consistency is maintained automatically (e.g. a fighter's record is corrected in `records.csv` whenever a result is saved).

## Analysis scripts

Located in `analysis/`, run independently of the app:

- **`analyse_fights.py`** — completed-fight counts, title vs. non-title splits, weight-class and date histograms, fighter appearance frequency, each fighter's most recent fight, stance/style matchup distributions, gym matchups, corner-win bias, and weigh-in/reach difference distributions.
- **`analyse_fighters.py`** — roster demographics: country and division breakdowns, stance/style splits, reach by division, KO-rate leaderboards, undefeated fighters, and an age-bucket histogram.
- **`analyse_judging.py`** — how judges actually score rounds: score-margin distribution and corner scoring bias, at the (fight, judge, round) level, as a foundation for later correlating punch stats with scorecards.

These scripts deliberately load the CSV/JSON data into an in-memory **SQLite** database and query it with hand-written SQL (`JOIN`, `GROUP BY`, `HAVING`, window functions, date arithmetic) rather than just filtering in pandas — the point is SQL practice, not just getting the numbers out.

## Getting started

**Requirements:** Python 3.10+, and the packages in `requirements.txt`.

```bash
pip install -r requirements.txt
python main.py
```

To run an analysis script:

```bash
python analysis/analyse_fights.py
```

## Roadmap

- Championship lineage tracking on a day-by-day basis (the monthly ranking snapshots can't cleanly represent title changes that happen mid-month)
- Post-fight changes feeding back into a fighter's next pre-fight scouting defaults (attributes/skills/tendencies currently carry forward manually)
- Correlating punch statistics with judges' scorecards
- Training predictive models for match outcomes, judge scoring, and P4P ranking movement

## Tech stack

Python, tkinter (UI), Pillow (flag images), SQLite (analysis only — the app itself stores data as CSV/JSON).
