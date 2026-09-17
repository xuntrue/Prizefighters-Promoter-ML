"""
Events.py

CRUD for event cards, stored as a single JSON array in data/events.json.
Unlike fights (potentially tens of thousands of rows, hence the CSV
index + one-file-per-fight split), events are few -- one per month or
so of play -- so there's no need to split them up or keep a separate
compressed index. A single JSON file holding a list of event objects is
the simplest thing that works.

An event has exactly one main event fight, zero or more co-main fights,
and zero or more undercard fights. All bouts on a card must share the
same Date -- a card happens on one night -- and must currently be in
Scheduled status (not already on another card, and not already fought).

This module validates fights exist, are Scheduled, and share a date,
but it does NOT flip their status to Evented itself -- that's an
orchestration step spanning two modules, so it belongs in
PrizefighterAPI.create_event(), same pattern as add_fighter() creating
a Records row.
"""

import json
import os

from api.Arenas import Arenas
from api.Fights import Fights, STATUS_SCHEDULED

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
EVENTS_FILE = os.path.join(DATA_DIR, "events.json")


class EventError(Exception):
    """Raised when an event card fails validation."""
    pass


class Events:
    """CRUD for event cards stored in events.json."""

    def __init__(self, filepath: str = EVENTS_FILE, arena_api: Arenas = None, fights_api: Fights = None):
        self.filepath = filepath
        self.arena_api = arena_api or Arenas()
        self.fights_api = fights_api or Fights()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump([], f)

    def get_all(self) -> list:
        self._ensure_file_exists()
        with open(self.filepath, encoding="utf-8") as f:
            return json.load(f)

    def get_by_id(self, event_id: int):
        for event in self.get_all():
            if event["event_id"] == event_id:
                return event
        return None

    def _save_all(self, events: list):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(sorted(events, key=lambda e: e["event_id"]), f, indent=2)

    def _next_id(self) -> int:
        existing = self.get_all()
        if not existing:
            return 1
        return max(e["event_id"] for e in existing) + 1

    def _validate(self, headliner, arena_id, date, main_event_fight_id,
                  co_main_fight_ids, undercard_fight_ids):
        headliner = headliner.strip()
        if not headliner:
            raise EventError("Headliner cannot be empty.")

        if not self.arena_api.exists(arena_id):
            raise EventError(f"No arena found with ArenaID {arena_id}.")

        if not main_event_fight_id:
            raise EventError("An event needs a main event fight.")

        all_fight_ids = [main_event_fight_id] + list(co_main_fight_ids) + list(undercard_fight_ids)

        if len(all_fight_ids) != len(set(all_fight_ids)):
            raise EventError("The same fight cannot appear twice on one card.")

        for fight_id in all_fight_ids:
            fight = self.fights_api.get_by_id(fight_id)
            if fight is None:
                raise EventError(f"No fight found with FightID {fight_id}.")
            if fight["status"] != STATUS_SCHEDULED:
                raise EventError(
                    f'Fight {fight_id} is {fight["status"]}, not Scheduled -- '
                    f"it can't be added to a card."
                )
            if fight["date"] != date:
                raise EventError(
                    f'Fight {fight_id} is scheduled for {fight["date"]}, not {date} -- '
                    f"every bout on a card must share the event's date."
                )

        return headliner

    def add(self, headliner: str, date: str, arena_id: int, main_event_fight_id: str,
            co_main_fight_ids: list = None, undercard_fight_ids: list = None,
            slogan: str = "") -> dict:
        co_main_fight_ids = list(co_main_fight_ids or [])
        undercard_fight_ids = list(undercard_fight_ids or [])

        headliner = self._validate(
            headliner, arena_id, date, main_event_fight_id, co_main_fight_ids, undercard_fight_ids
        )

        new_event = {
            "event_id": self._next_id(),
            "headliner": headliner,
            "slogan": slogan.strip(),
            "arena_id": arena_id,
            "date": date,
            "main_event_fight_id": main_event_fight_id,
            "co_main_fight_ids": co_main_fight_ids,
            "undercard_fight_ids": undercard_fight_ids,
        }

        existing = self.get_all()
        existing.append(new_event)
        self._save_all(existing)
        return new_event

    def delete(self, event_id: int) -> None:
        existing = self.get_all()
        remaining = [e for e in existing if e["event_id"] != event_id]
        if len(remaining) == len(existing):
            raise EventError(f"No event found with EventID {event_id}.")
        self._save_all(remaining)
