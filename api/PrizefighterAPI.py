"""
PrizefighterAPI.py

Central facade for all data access in the Prizefighters Promoter ML app.
UI code should never touch files under data/ directly -- it should only
ever call through this class. This keeps storage details (CSV today,
maybe SQLite later) hidden from the UI layer, and gives one place to
coordinate logic that spans more than one table (e.g. creating a
zeroed-out record whenever a new fighter is added).
"""

from api.Weight_Classes import WeightClasses, WeightClassError  # noqa: F401
from api.Country import Country, CountryError, CountryFlags, CountryFlagError  # noqa: F401
from api.Fighter import Fighter, FighterError  # noqa: F401
from api.Records import Records, RecordError  # noqa: F401
from api.Rankings import (  # noqa: F401
    Rankings, RankingError, TYPE_DIVISION, TYPE_P4P, MAX_FAN_RANKS,
)

class PrizefighterAPI:
    """Single entry point the UI layer talks to."""

    def __init__(self):
        self.weight_classes = WeightClasses()
        self.countries = Country()
        self.flags = CountryFlags(country_api=self.countries)
        self.fighters = Fighter()
        self.records = Records()
        self.rankings = Rankings(fighter_api=self.fighters, records_api=self.records)

    # ---- Weight class passthroughs ----
    def get_weight_classes(self):
        return self.weight_classes.get_all()

    def add_weight_class(self, weight_limit: int, weight_class: str):
        self.weight_classes.add(weight_limit, weight_class)

    def update_weight_class(self, old_weight_limit: int, new_weight_limit: int, new_weight_class: str):
        self.weight_classes.update(old_weight_limit, new_weight_limit, new_weight_class)

    def delete_weight_class(self, weight_limit: int):
        self.weight_classes.delete(weight_limit)

    # ---- Country passthroughs (read-only in the UI today, full CRUD available) ----

    def get_countries(self):
        return self.countries.get_all()

    def add_country(self, a2: str, country_name: str):
        self.countries.add(a2, country_name)

    def update_country(self, a2: str, new_country_name: str):
        self.countries.update(a2, new_country_name)

    def delete_country(self, a2: str):
        self.countries.delete(a2)

    # ---- Country flags (read-only in the UI today, full CRUD available) ----
    def get_flag_path(self, a2: str):
        return self.flags.get_path(a2)

    def get_all_flags(self):
        return self.flags.get_all()

    def add_flag(self, a2: str, source_path: str):
        self.flags.add(a2, source_path)

    def update_flag(self, a2: str, source_path: str):
        self.flags.update(a2, source_path)

    def delete_flag(self, a2: str):
        self.flags.delete(a2)

    # ---- Fighters ----
    def get_fighters(self):
        return self.fighters.get_all()

    def get_fighter(self, fighter_id: int):
        return self.fighters.get_by_id(fighter_id)

    def search_fighters(self, first_name: str = "", last_name: str = ""):
        return self.fighters.search_by_name(first_name, last_name)

    def add_fighter(self, wins: int = 0, knockouts: int = 0, losses: int = 0, draws: int = 0,
                     **fighter_fields) -> dict:
        """
        Add a fighter, then create their record. Defaults to a zeroed-out
        debut record; pass wins/knockouts/losses/draws for a veteran
        fighter hired with a pre-existing record.
        """
        new_fighter = self.fighters.add(**fighter_fields)
        self.records.create(new_fighter["fighter_id"], wins, knockouts, losses, draws)
        return new_fighter

    def update_fighter(self, fighter_id: int, **fighter_fields) -> None:
        self.fighters.update(fighter_id, **fighter_fields)

    def delete_fighter(self, fighter_id: int) -> None:
        """Delete a fighter and their record together."""
        self.fighters.delete(fighter_id)
        try:
            self.records.delete(fighter_id)
        except RecordError:
            pass  # record may already be missing; fighter deletion still succeeds

    # ---- Records ----

    def get_record(self, fighter_id: int):
        return self.records.get_by_fighter_id(fighter_id)

    def update_record(self, fighter_id: int, wins: int, knockouts: int, losses: int, draws: int) -> None:
        self.records.update(fighter_id, wins, knockouts, losses, draws)

    # ---- Rankings (divisional + P4P) ----

    def get_ranking_snapshot(self, month: str, ranking_type: str, weight_limit=None):
        return self.rankings.get_snapshot(month, ranking_type, weight_limit)

    def get_ranking_months(self, ranking_type: str = None, weight_limit=None):
        return self.rankings.get_months(ranking_type, weight_limit)

    def save_ranking_snapshot(self, month: str, ranking_type: str, entries: list, weight_limit=None):
        self.rankings.save_snapshot(month, ranking_type, entries, weight_limit)

    def delete_ranking_snapshot(self, month: str, ranking_type: str, weight_limit=None):
        self.rankings.delete_snapshot(month, ranking_type, weight_limit)

    def carry_forward_rankings(self, ranking_type: str, weight_limit=None, from_month: str = None):
        return self.rankings.carry_forward(ranking_type, weight_limit, from_month)

    # ---- Fan rankings ----
    def get_fan_snapshot(self, month: str):
        return self.rankings.get_fan_snapshot(month)

    def get_fan_months(self):
        return self.rankings.get_fan_months()

    def save_fan_snapshot(self, month: str, entries: list):
        self.rankings.save_fan_snapshot(month, entries)

    def delete_fan_snapshot(self, month: str):
        self.rankings.delete_fan_snapshot(month)

    def carry_forward_fan_rankings(self, from_month: str = None):
        return self.rankings.carry_forward_fans(from_month)
