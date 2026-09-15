import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

RECORDS_FILE = os.path.join(DATA_DIR, "records.csv")

FIELDNAMES = ["FighterID", "Wins", "Knockouts", "Losses", "Draws"]

class RecordError(Exception):
    """Raised when a record fails validation."""
    pass

class Records:
    def __init__(self, filepath: str = RECORDS_FILE):
        self.filepath = filepath
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
    
    # --- CREATE ---
    def create_default(self, fighter_id: int) -> None:
        """Create a zeroed-out record row for a newly added fighter """
        existing = self.get_all()
        if any(row["fighter_id"] == fighter_id for row in existing):
            raise RecordError(f"A record for FighterID {fighter_id} already exists.")

        existing.append({"fighter_id": fighter_id, "wins": 0, "knockouts": 0, "losses": 0, "draws": 0})
        self._save_all(existing)

    # --- READ ---
    def get_all(self) -> list:
        self._ensure_file_exists()
        with open(self.filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                {
                    "fighter_id": int(row["FighterID"]),
                    "wins": int(row["Wins"]),
                    "knockouts": int(row["Knockouts"]),
                    "losses": int(row["Losses"]),
                    "draws": int(row["Draws"]),
                }
                for row in reader
            ]
        return sorted(rows, key=lambda r: r["fighter_id"])

    def get_by_fighter_id(self, fighter_id: int):
        for row in self.get_all():
            if row["fighter_id"] == fighter_id:
                return row
        return None

    def _save_all(self, rows: list):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in sorted(rows, key=lambda r: r["fighter_id"]):
                writer.writerow(
                    {
                        "FighterID": row["fighter_id"],
                        "Wins": row["wins"],
                        "Knockouts": row["knockouts"],
                        "Losses": row["losses"],
                        "Draws": row["draws"],
                    }
                )

  
    # --- UPDATE ---
    def update(self, fighter_id: int, wins: int, knockouts: int, losses: int, draws: int) -> None:
        if min(wins, knockouts, losses, draws) < 0:
            raise RecordError("Record values cannot be negative.")
        if knockouts > wins:
            raise RecordError("Knockouts cannot exceed total wins.")

        existing = self.get_all()
        if not any(row["fighter_id"] == fighter_id for row in existing):
            raise RecordError(f"No record found for FighterID {fighter_id}.")

        others = [row for row in existing if row["fighter_id"] != fighter_id]
        others.append(
            {"fighter_id": fighter_id, "wins": wins, "knockouts": knockouts, "losses": losses, "draws": draws}
        )
        self._save_all(others)

    # --- DELETE ---
    def delete(self, fighter_id: int) -> None:
        existing = self.get_all()
        remaining = [row for row in existing if row["fighter_id"] != fighter_id]

        if len(remaining) == len(existing):
            raise RecordError(f"No record found for FighterID {fighter_id}.")

        self._save_all(remaining)
