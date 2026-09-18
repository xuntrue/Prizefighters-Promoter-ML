import copy

from datetime import datetime

from api.Weight_Classes import WeightClasses, WeightClassError 
from api.Country import Country, CountryError, CountryFlags, CountryFlagError
from api.Fighter import Fighter, FighterError, blank_meta_section, validate_meta_section
from api.Records import Records, RecordError
from api.Rankings import Rankings, RankingError, TYPE_DIVISION, TYPE_P4P, MAX_FAN_RANKS
from api.Arenas import Arenas, ArenaError 
from api.Fights import Fights, FightError, STATUS_SCHEDULED, STATUS_EVENTED, STATUS_META, DATE_FORMAT
from api.Events import Events, EventError 


class PrizefighterAPI:
    """Single entry point the UI layer talks to."""

    def __init__(self):
        self.weight_classes = WeightClasses()
        self.countries = Country()
        self.flags = CountryFlags(country_api=self.countries)
        self.fighters = Fighter()
        self.records = Records()
        self.rankings = Rankings(fighter_api=self.fighters, records_api=self.records)
        self.arenas = Arenas(country_api=self.countries)
        self.fights = Fights(fighter_api=self.fighters)
        self.events = Events(arena_api=self.arenas, fights_api=self.fights)

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

    def get_next_ranking_month(self, ranking_type: str, weight_limit=None):
        return self.rankings.get_next_month(ranking_type, weight_limit)

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

    def get_next_fan_month(self):
        return self.rankings.get_next_fan_month()

    def save_fan_snapshot(self, month: str, entries: list):
        self.rankings.save_fan_snapshot(month, entries)

    def delete_fan_snapshot(self, month: str):
        self.rankings.delete_fan_snapshot(month)

    def carry_forward_fan_rankings(self, from_month: str = None):
        return self.rankings.carry_forward_fans(from_month)

    # ---- Arenas ----

    def get_arenas(self):
        return self.arenas.get_all()

    def get_arena(self, arena_id: int):
        return self.arenas.get_by_id(arena_id)

    def add_arena(self, name: str, country: str):
        return self.arenas.add(name, country)

    def update_arena(self, arena_id: int, name: str, country: str):
        self.arenas.update(arena_id, name, country)

    def delete_arena(self, arena_id: int):
        self.arenas.delete(arena_id)

    # ---- Fights ----

    def get_fights(self):
        return self.fights.get_all()

    def get_fight(self, fight_id: str):
        return self.fights.get_by_id(fight_id)

    def get_fight_full(self, fight_id: str):
        return self.fights.get_full(fight_id)

    def get_fights_by_status(self, status: str):
        return self.fights.get_by_status(status)

    def get_scheduled_fights_on_date(self, date: str):
        return self.fights.get_scheduled_on_date(date)

    def get_fights_by_fighter(self, fighter_id: int):
        return self.fights.get_by_fighter(fighter_id)

    def get_championship_fights(self, weight_limit=None):
        return self.fights.get_championship_fights(weight_limit)

    def schedule_fight(self, date: str, weight_limit: int, red_corner_fighter_id: int,
                       blue_corner_fighter_id: int, rounds: int, round_minutes: int,
                       championship: bool = False) -> dict:
        return self.fights.schedule(
            date, weight_limit, red_corner_fighter_id, blue_corner_fighter_id,
            rounds, round_minutes, championship,
        )

    def cancel_fight(self, fight_id: str) -> None:
        self.fights.cancel(fight_id)

    def delete_fight(self, fight_id: str) -> None:
        self.fights.delete(fight_id)

    # ---- Events ----

    def get_events(self):
        return self.events.get_all()

    def get_event(self, event_id: int):
        return self.events.get_by_id(event_id)

    def create_event(self, headliner: str, date: str, arena_id: int, main_event_fight_id: str,
                     co_main_fight_ids: list = None, undercard_fight_ids: list = None,
                     slogan: str = "") -> dict:
        """
        Create an event card, then flip every included fight's status to
        Evented. Events.add() already validated every fight exists, is
        Scheduled, and shares the card's date -- so the status updates
        below shouldn't fail, but if one somehow does, the event is
        rolled back rather than left referencing a fight whose status
        didn't actually change.
        """
        new_event = self.events.add(
            headliner, date, arena_id, main_event_fight_id,
            co_main_fight_ids, undercard_fight_ids, slogan,
        )

        all_fight_ids = (
            [main_event_fight_id]
            + list(co_main_fight_ids or [])
            + list(undercard_fight_ids or [])
        )

        updated = []
        try:
            for fight_id in all_fight_ids:
                self.fights.update_status(fight_id, STATUS_EVENTED)
                self.fights.set_event_id(fight_id, new_event["event_id"])
                updated.append(fight_id)
        except FightError:
            for fight_id in updated:
                self.fights.update_status(fight_id, STATUS_SCHEDULED)
                self.fights.set_event_id(fight_id, None)
            self.events.delete(new_event["event_id"])
            raise

        return new_event

    def delete_event(self, event_id: int) -> None:
        """Delete an event card and revert its fights back to Scheduled,
        so they can be re-assigned to a different card."""
        event = self.events.get_by_id(event_id)
        if event is None:
            raise EventError(f"No event found with EventID {event_id}.")

        all_fight_ids = (
            [event["main_event_fight_id"]]
            + event["co_main_fight_ids"]
            + event["undercard_fight_ids"]
        )
        for fight_id in all_fight_ids:
            self.fights.update_status(fight_id, STATUS_SCHEDULED)
            self.fights.set_event_id(fight_id, None)

        self.events.delete(event_id)

    # ---- Pre-fight metadata ----

    CORNERS = ("red_corner", "blue_corner")

    def _corner_fighter_id(self, fight: dict, corner: str) -> int:
        if corner not in self.CORNERS:
            raise FightError(f"corner must be one of {self.CORNERS}.")
        return fight["red_corner_fighter_id"] if corner == "red_corner" else fight["blue_corner_fighter_id"]

    def get_default_meta_for_fighter(self, fight_id: str, corner: str) -> dict:
        """
        Build a starting point for the pre-fight meta form ("_load_default").

        attributes/skills/tendencies/career_stats/last_6 are carried
        forward from the fighter's most recently recorded meta -- their
        most recent OTHER fight (by date) that has meta saved for them,
        regardless of which corner they were in that fight. If they have
        no prior recorded meta at all (a debut fighter, or one whose
        earlier fights predate this feature), a blank default is used
        instead.

        profile.record and profile.weigh_in are NOT carried forward --
        record always reflects the live value in records.csv (the
        source of truth), and weigh-in is fight-specific with no
        meaningful previous value, so it defaults to this fight's own
        weight_limit as a starting guess for the user to adjust down.
        """
        fight = self.fights.get_by_id(fight_id)
        if fight is None:
            raise FightError(f"No fight found with FightID {fight_id}.")

        fighter_id = self._corner_fighter_id(fight, corner)

        base = None
        other_fights = sorted(
            (f for f in self.fights.get_by_fighter(fighter_id) if f["fight_id"] != fight_id),
            key=lambda f: datetime.strptime(f["date"], DATE_FORMAT),
            reverse=True,
        )
        for candidate in other_fights:
            full = self.fights.get_full(candidate["fight_id"])
            if not full:
                continue
            candidate_corner = (
                "red_corner" if full["red_corner_fighter_id"] == fighter_id else "blue_corner"
            )
            prior_meta = (full.get("meta") or {}).get(candidate_corner)
            if prior_meta:
                base = copy.deepcopy(prior_meta)
                break

        if base is None:
            base = blank_meta_section(fight["weight_limit"])

        current_record = self.records.get_by_fighter_id(fighter_id)
        base["profile"]["record"] = (
            {k: current_record[k] for k in ("wins", "knockouts", "losses", "draws")}
            if current_record else {"wins": 0, "knockouts": 0, "losses": 0, "draws": 0}
        )
        base["profile"]["weigh_in"] = fight["weight_limit"] - 1

        return base

    def save_fight_meta(self, fight_id: str, corner: str, meta: dict) -> None:
        """ Validate and save one corner's pre-fight meta into the fight's JSON file """
        fight = self.fights.get_by_id(fight_id)
        if fight is None:
            raise FightError(f"No fight found with FightID {fight_id}.")
        if fight["status"] not in (STATUS_EVENTED, STATUS_META):
            raise FightError(
                f'Fight {fight_id} is {fight["status"]} -- pre-fight meta can only be '
                f"recorded once a fight has been added to an event card."
            )

        fighter_id = self._corner_fighter_id(fight, corner)
        min_weigh_in = self.weight_classes.get_min_weigh_in(fight["weight_limit"])
        cleaned = validate_meta_section(meta, fight["weight_limit"], min_weigh_in)

        full = self.fights.get_full(fight_id)
        meta_obj = dict(full.get("meta") or {})
        meta_obj[corner] = cleaned
        self.fights.save_meta(fight_id, meta_obj)

        record = cleaned["profile"]["record"]
        self.records.update(fighter_id, record["wins"], record["knockouts"],
                            record["losses"], record["draws"])

        if all(c in meta_obj for c in self.CORNERS):
            self.fights.update_status(fight_id, STATUS_META)
