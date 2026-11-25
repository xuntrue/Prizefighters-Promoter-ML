import datetime

import pandas as pd

from ._storage import CsvTable

COLUMNS = ["arena_id", "arena_name", "country", "city", "capacity", "foundered"]
FOUNDED = "founded"

_table = CsvTable("arenas.csv", key="arena_id", columns=COLUMNS)

def _validate(record):
    if "arena_name" in record and not str(record["arena_name"]).strip():
        raise ValueError("arena_name cannot be empty")
    if "country" in record and not (len(str(record["country"])) == 2 and str(record["country"]).isupper()):
        raise ValueError(f"country must be a two-letter uppercase code, got {record['country']!r}")
    if "capacity" in record and int(record["capacity"]) <= 0:
        raise ValueError("capacity must be a positive whole number")
    if FOUNDED in record:
        year = int(record[FOUNDED])
        if not 1800 <= year <= datetime.date.today().year:
            raise ValueError(f"{FOUNDED} must be between 1800 and this year, got {year}")

# --- CREATE ---
def create(arena_name, country, city, capacity, founded):
    record = {"arena_name": arena_name, "country": country, "city": city,
              "capacity": int(capacity), FOUNDED: int(founded)}
    _validate(record)
    ids = pd.to_numeric(_table.all()["arena_id"])
    record["arena_id"] = int(ids.max()) + 1 if len(ids) else 1  # auto-increment
    _table.create(record)
    return get(record["arena_id"])

# --- READ ---
def get_all():
    """All arenas, with numeric columns converted to integers."""
    df = _table.all()
    for column in ("arena_id", "capacity", FOUNDED):
        df[column] = pd.to_numeric(df[column]).astype(int)
    return df

def get(arena_id):
    record = _table.get(arena_id)
    for column in ("arena_id", "capacity", FOUNDED):
        record[column] = int(record[column])
    return record

# --- UPDATE ---
def update(arena_id, **changes):
    if "founded" in changes and FOUNDED != "founded":
        changes[FOUNDED] = changes.pop("founded")
    _validate(changes)
    _table.update(arena_id, changes)
    return get(arena_id)

# --- DELETE ---
def delete(arena_id):
    _table.delete(arena_id)