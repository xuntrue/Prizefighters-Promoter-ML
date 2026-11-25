import re

from ._storage import CsvTable

CODE = "A-2"
NAME = "CountryName"

_table = CsvTable("countries.csv", key=CODE, columns=[CODE, NAME])

def _check_code(code):
    if not re.fullmatch(r"[A-Z]{2}", str(code)):
        raise ValueError(f"Country code must be two uppercase letters, got {code!r}")

# --- CREATE ---
def create(code, name):
    _check_code(code)
    if not str(name).strip():
        raise ValueError("Country name cannot be empty")
    return _table.create({CODE: code, NAME: name.strip()})

# --- READ ---
def get_all():
    df = _table.all()
    df[CODE] = df[CODE].str.strip()
    return df

def get(code):
    return _table.get(code)

def exists(code):
    return _table.exists(code)

# -- UPDATE ---
def update(code, name):
    if not str(name).strip():
        raise ValueError("Country name cannot be empty")
    return _table.update(code, {NAME: name.strip()})

# --- DELETE ---
def delete(code):
    _table.delete(code)