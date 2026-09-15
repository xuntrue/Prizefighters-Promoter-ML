from api.Country import Country, CountryError
from api.Fighter import Fighter, FighterError
from api.Records import Records, RecordError
from api.Weight_Classes import WeightClasses, WeightClassError

class PrizefighterAPI:
    def __init__(self):
        self.countries = Country()
        self.fighters = Fighter()
        self.records = Records()
        self.weight_classes = WeightClasses()

    # ---- Country  ----
    def get_countries(self):
        return self.countries.get_all()

    def add_country(self, a2: str, country_name: str):
        self.countries.add(a2, country_name)

    def update_country(self, a2: str, new_country_name: str):
        self.countries.update(a2, new_country_name)

    def delete_country(self, a2: str):
        self.countries.delete(a2)

    # ---- Fighters ----
    def get_fighters(self):
        return self.fighters.get_all()

    def get_fighter(self, fighter_id: int):
        return self.fighters.get_by_id(fighter_id)

    def search_fighters(self, first_name: str = "", last_name: str = ""):
        return self.fighters.search_by_name(first_name, last_name)

    def add_fighter(self, **fighter_fields) -> dict:
        """ Add a fighter, then create a zeroed-out record for them """
        new_fighter = self.fighters.add(**fighter_fields)
        self.records.create_default(new_fighter["fighter_id"])
        return new_fighter

    def update_fighter(self, fighter_id: int, **fighter_fields) -> None:
        self.fighters.update(fighter_id, **fighter_fields)

    def delete_fighter(self, fighter_id: int) -> None:
        """ Delete a fighter and their record together """
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

    # ---- Weight class passthroughs ----
    def get_weight_classes(self):
        return self.weight_classes.get_all()

    def add_weight_class(self, weight_limit: int, weight_class: str):
        self.weight_classes.add(weight_limit, weight_class)

    def update_weight_class(self, old_weight_limit: int, new_weight_limit: int, new_weight_class: str):
        self.weight_classes.update(old_weight_limit, new_weight_limit, new_weight_class)

    def delete_weight_class(self, weight_limit: int):
        self.weight_classes.delete(weight_limit)
