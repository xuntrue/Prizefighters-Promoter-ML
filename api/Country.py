import csv
import os
import shutil

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

COUNTRIES_FILE = os.path.join(DATA_DIR, "countries.csv")
FLAGS_DIR = os.path.join(DATA_DIR, "country_flags")

FIELDNAMES = ["A-2", "CountryName"]

class CountryError(Exception):
    """Raised when a country entry fails validation"""
    pass


class Country:
    def __init__(self, filepath: str = COUNTRIES_FILE):
        self.filepath = filepath
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()

    # --- CREATE ---
    def add(self, a2: str, country_name: str) -> None:
        a2 = a2.strip().upper()
        country_name = country_name.strip()

        if len(a2) != 2 or not a2.isalpha():
            raise CountryError("Country code must be exactly 2 letters (ISO 3166-1 alpha-2).")
        if not country_name:
            raise CountryError("Country name cannot be empty.")

        existing = self.get_all()

        if any(row["a2"] == a2 for row in existing):
            raise CountryError(f'Country code "{a2}" already exists.')
        if any(row["country_name"].lower() == country_name.lower() for row in existing):
            raise CountryError(f'Country "{country_name}" already exists.')

        existing.append({"a2": a2, "country_name": country_name})
        self._save_all(existing)

    # --- READ ---
    def get_all(self) -> list:
        """Return all countries as a list of dicts, sorted by A-2 code"""
        self._ensure_file_exists()
        with open(self.filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                {"a2": row["A-2"].strip().upper(), "country_name": row["CountryName"].strip()}
                for row in reader
            ]
        return sorted(rows, key=lambda r: r["a2"]) # sort

    def get_by_code(self, a2: str):
        """Return the country dict for the given A-2 code, or None if not found."""
        a2 = a2.strip().upper()
        for row in self.get_all():
            if row["a2"] == a2:
                return row
        return None

    def exists(self, a2: str) -> bool:
        return self.get_by_code(a2) is not None

    def _save_all(self, rows: list):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["country_name"]):
                writer.writerow({"A-2": row["a2"], "CountryName": row["country_name"]})
    
    # --- UPDATE ---
    def update(self, a2: str, new_country_name: str) -> None:
        a2 = a2.strip().upper()
        new_country_name = new_country_name.strip()

        if not new_country_name:
            raise CountryError("Country name cannot be empty.")

        existing = self.get_all()
        if not any(row["a2"] == a2 for row in existing):
            raise CountryError(f'No country found with code "{a2}".')

        others = [row for row in existing if row["a2"] != a2]
        if any(row["country_name"].lower() == new_country_name.lower() for row in others):
            raise CountryError(f'Country "{new_country_name}" already exists.')

        others.append({"a2": a2, "country_name": new_country_name})
        self._save_all(others)

    # --- DELETE ---
    def delete(self, a2: str) -> None:
        a2 = a2.strip().upper()
        existing = self.get_all()
        remaining = [row for row in existing if row["a2"] != a2]

        if len(remaining) == len(existing):
            raise CountryError(f'No country found with code "{a2}".')

        self._save_all(remaining)


class CountryFlagError(Exception):
    """Raised when a flag operation fails validation."""
    pass


class CountryFlags:
    def __init__(self, flags_dir: str = FLAGS_DIR, country_api: Country = None):
        self.flags_dir = flags_dir
        self.country_api = country_api or Country()
        os.makedirs(self.flags_dir, exist_ok=True)

    def _flag_path(self, a2: str) -> str:
        return os.path.join(self.flags_dir, f"{a2.strip().upper()}.png")

    # --- CREATE ---
    def add(self, a2: str, source_filepath: str) -> None:
        """Copy a new flag PNG in for a country that doesn't have one yet."""
        a2 = a2.strip().upper()

        if not self.country_api.exists(a2):
            raise CountryFlagError(f'Country code "{a2}" was not found in countries.csv.')
        if self.exists(a2):
            raise CountryFlagError(f'A flag for "{a2}" already exists -- use update() to replace it.')
        if not os.path.exists(source_filepath):
            raise CountryFlagError(f'Source file "{source_filepath}" does not exist.')
        if not source_filepath.lower().endswith(".png"):
            raise CountryFlagError("Flag images must be .png files.")

        shutil.copyfile(source_filepath, self._flag_path(a2))

    # --- READ ---
    def get_all(self) -> list:
        """Return every flag currently on disk as a list of {a2, path} dicts """
        flags = []
        for filename in sorted(os.listdir(self.flags_dir)):
            if filename.lower().endswith(".png"):
                a2 = filename[:-4].upper()
                flags.append({"a2": a2, "path": os.path.join(self.flags_dir, filename)})
        return flags

    def get_path(self, a2: str):
        """Return the absolute path to the flag for this A-2 code, or None
        if no flag file exists for it."""
        path = self._flag_path(a2)
        return path if os.path.exists(path) else None

    def exists(self, a2: str) -> bool:
        return self.get_path(a2) is not None

    # --- UPDATE ---
    def update(self, a2: str, source_filepath: str) -> None:
        """Replace an existing flag PNG."""
        a2 = a2.strip().upper()

        if not self.exists(a2):
            raise CountryFlagError(f'No existing flag found for "{a2}" -- use add() instead.')
        if not os.path.exists(source_filepath):
            raise CountryFlagError(f'Source file "{source_filepath}" does not exist.')
        if not source_filepath.lower().endswith(".png"):
            raise CountryFlagError("Flag images must be .png files.")

        shutil.copyfile(source_filepath, self._flag_path(a2))

    # --- DELETE ---
    def delete(self, a2: str) -> None:
        path = self.get_path(a2)
        if path is None:
            raise CountryFlagError(f'No flag found for "{a2}".')
        os.remove(path)
