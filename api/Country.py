import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
COUNTRIES_FILE = os.path.join(DATA_DIR, "countries.csv")
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
        """Return all countries as a list of dicts, sorted by country_name."""
        self._ensure_file_exists()
        with open(self.filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                {"a2": row["A-2"].strip().upper(), "country_name": row["CountryName"].strip()}
                for row in reader
            ]
        return sorted(rows, key=lambda r: r["country_name"])

    def get_by_code(self, a2: str):
        """Return the country dict for the given A-2 code, or None if not found."""
        a2 = a2.strip().upper()
        for row in self.get_all():
            if row["a2"] == a2:
                return row
        return None

    def exists(self, a2: str) -> bool:
        return self.get_by_code(a2) is not None
    
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

    def _save_all(self, rows: list):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["country_name"]):
                writer.writerow({"A-2": row["a2"], "CountryName": row["country_name"]})

    # --- DELETE ---
    def delete(self, a2: str) -> None:
        a2 = a2.strip().upper()
        existing = self.get_all()
        remaining = [row for row in existing if row["a2"] != a2]

        if len(remaining) == len(existing):
            raise CountryError(f'No country found with code "{a2}".')

        self._save_all(remaining)
