import csv
import os

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
WEIGHTS_FILE = os.path.join(DATA_DIR, "weights.csv")

MIN_WEIGHT = 100
MAX_WEIGHT = 300

FIELDNAMES = ["weight_limit", "weight_class"]

class WeightClassError(Exception):
    """ Raised when a weight class fails validation """
    pass


class WeightClasses:
    def __init__(self, filepath: str = WEIGHTS_FILE):
        self.filepath = filepath
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()

    # --- CREATE ---
    def add(self, weight_limit: int, weight_class: str) -> None:
        """ Add a new weight class """
        weight_class = weight_class.strip()

        if not (MIN_WEIGHT <= weight_limit <= MAX_WEIGHT):
            raise WeightClassError(f"Weight limit must be between {MIN_WEIGHT} and {MAX_WEIGHT} lbs (inclusive)")

        if not weight_class:
            raise WeightClassError("Weight class name cannot be empty")

        existing = self.get_all()

        if any(row["weight_limit"] == weight_limit for row in existing):
            raise WeightClassError(
                f"A weight class with limit {weight_limit} lbs already exists"
            )

        if any(row["weight_class"].lower() == weight_class.lower() for row in existing):
            raise WeightClassError(f'A weight class named "{weight_class}" already exists')

        existing.append({"weight_limit": weight_limit, "weight_class": weight_class})
        self._save_all(existing)

    # --- READ ---
    def get_all(self) -> list:
        """Return all weight classes"""
        self._ensure_file_exists()
        with open(self.filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                {
                    "weight_limit": int(row["weight_limit"]),
                    "weight_class": row["weight_class"],
                }
                for row in reader
            ]
        return sorted(rows, key=lambda r: r["weight_limit"])

    def _save_all(self, rows: list):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["weight_limit"]):
                writer.writerow(row)
    
    # --- UPDATE ---
    def update(self, old_weight_limit: int, new_weight_limit: int, new_weight_class: str) -> None:
        """ Update an existing weight class """
        new_weight_class = new_weight_class.strip()

        if not (MIN_WEIGHT <= new_weight_limit <= MAX_WEIGHT):
            raise WeightClassError(f"Weight limit must be between {MIN_WEIGHT} and {MAX_WEIGHT} lbs (inclusive)")

        if not new_weight_class:
            raise WeightClassError("Weight class name cannot be empty")

        existing = self.get_all()

        if not any(row["weight_limit"] == old_weight_limit for row in existing):
            raise WeightClassError(f"No weight class found with limit {old_weight_limit} lbs")

        others = [row for row in existing if row["weight_limit"] != old_weight_limit]

        if any(row["weight_limit"] == new_weight_limit for row in others):
            raise WeightClassError(f"A weight class with limit {new_weight_limit} lbs already exists")

        if any(row["weight_class"].lower() == new_weight_class.lower() for row in others):
            raise WeightClassError(f'A weight class named "{new_weight_class}" already exists')

        others.append({"weight_limit": new_weight_limit, "weight_class": new_weight_class})
        self._save_all(others)

    # --- DELETE ---
    def delete(self, weight_limit: int) -> None:
        """Delete a weight class"""
        existing = self.get_all()
        remaining = [row for row in existing if row["weight_limit"] != weight_limit]

        if len(remaining) == len(existing):
            raise WeightClassError(f"No weight class found with limit {weight_limit} lbs.")

        self._save_all(remaining)
