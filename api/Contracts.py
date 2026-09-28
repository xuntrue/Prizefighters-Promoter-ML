import csv
import os

from datetime import datetime
from typing import Optional

from api.Fighter import Fighter
from api.Gyms import Gyms

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

CONTRACTS_FILE = os.path.join(DATA_DIR, "contracts.csv")
FIELDNAMES = [
        "contractID",
        "gymID",
        "fighterID",
        "startDate",
        "endDate",
    ]
DATE_FORMAT = "%m-%d-%Y"

class ContractError(Exception):
    """ Raised when a contract fails validation or cannot be saved """

class Contracts:
    """ Manage gym contracts between fighters and gyms """
    def __init__(self, filepath: str = CONTRACTS_FILE):
        self.filepath = filepath
        self._ensure_file_exists() # Ensure the directory exists

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()

    def get_all(self) -> list:
        self._ensure_file_exists()
        with open(self.filepath, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            rows = [self._row_from_csv(row) for row in reader]
        return sorted(rows, key=lambda r: r["contractID"])

    def get_by_fighter(self, fighter_id) -> list:
        """ Return all contracts associated with a fighter """
        return [
            contract
            for contract in self.get_all()
            if contract["fighterID"] == str(fighter_id)
        ]

    def get_by_gym(self, gym_id) -> list:
        """ Return all contracts associated with a gym """
        return [
            contract
            for contract in self.get_all()
            if contract["gymID"] == str(gym_id)
        ]

    def get_by_id(self, contract_id) -> Optional[dict]:
        """ Return a contract by its ID, or None if not found """
        contract_id = str(contract_id)
        for contract in self.get_all():
            if contract["contractID"] == contract_id:
                return contract
        return None

    def _write_all(self, contracts: list) -> None:
        """ Rewrite the entire contracts CSV """
        with open(self.filepath, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(contracts)

    def _generate_contract_id(self) -> str:
        """ Generate the next sequential contract ID """
        contracts = self.get_all()
        if not contracts:
            return 1
        ids = [
            int(contract["contractID"])
            for contract in contracts
            if contract["contractID"].isdigit()
        ]
        return max(ids, default=0)+1

    @staticmethod
    def _parse_date(date_string: str) -> datetime:
        """Parse a date in MM-DD-YYYY format."""
        try:
            return datetime.strptime(date_string, "%m-%d-%Y")
        except (ValueError, TypeError):
            raise ContractError(
                f"Invalid date '{date_string}'. "
                "Expected format: MM-DD-YYYY"
            )

    def _validate_dates(self, start_date: str, end_date: str) -> tuple:
        """ Validate and parse a contract's start and end dates """
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        if start > end:
            raise ContractError("The contract's start date cannot be after its end date")
        return start, end

    def validate_contract(self, gym_id: int, fighter_id: int, start_date: str, end_date: str, exclude_contract_id=None,) -> bool:
        """ Validate a proposed new contract. A fighter cannot have overlapping contracts. """
        if gym_id is None or str(gym_id).strip() == "":
            raise ContractError("Please select a gym")
        if fighter_id is None or str(fighter_id).strip() == "":
            raise ContractError("Please select a fighter")

        new_start, new_end = self._validate_dates(start_date, end_date,)
        existing_contracts = self.get_by_fighter(fighter_id)
        for contract in existing_contracts:

            # Ignore the contract being edited (if applicable)
            if (
                exclude_contract_id is not None
                and contract["contractID"] == str(exclude_contract_id)
            ):
                continue

            existing_start = self._parse_date(contract["startDate"])
            existing_end = self._parse_date(contract["endDate"])

            # Inclusive date-range overlap check
            overlaps = (
                new_start <= existing_end
                and existing_start <= new_end
            )

            if overlaps:
                raise ContractError(
                    f"Contract overlaps with existing contract "
                    f"{contract['contractID']} "
                    f"({contract['startDate']} to {contract['endDate']})."
                )

        return True

    def save_contract(self, gym_id : int, fighter_id : int, start_date: str, end_date: str,) -> dict:
        """ Validate and save a new contract """
        self.validate_contract(gym_id=gym_id, fighter_id=fighter_id, start_date=start_date, end_date=end_date)
        contract = {
            "contractID": self._generate_contract_id(),
            "gymID": str(gym_id),
            "fighterID": str(fighter_id),
            "startDate": start_date,
            "endDate": end_date,
        }
        contracts = self.get_all()
        contracts.append(contract)
        self._write_all(contracts)
        return contract

    def delete_contract(self, contract_id) -> bool:
        """ Delete a contract by ID """
        contract_id = str(contract_id)
        contracts = self.get_all()
        updated_contracts = [
            contract
            for contract in contracts
            if contract["contractID"] != contract_id
        ]

        if len(updated_contracts) == len(contracts):
            return False
        self._write_all(updated_contracts)
        return True

    def get_active_contract(self, fighter_id, date: str,) -> Optional[dict]:
        """ Return the contract active for a fighter on a given date """
        check_date = self._parse_date(date)
        for contract in self.get_by_fighter(fighter_id):
            start = self._parse_date(contract["startDate"])
            end = self._parse_date(contract["endDate"])

            if start <= check_date <= end:
                return contract

        return None