from . import arenas as _arenas
from . import countries as _countries
from . import flags as _flags
from ._storage import NotFoundError, DuplicateError

class PrizeFighterAPI:
    NotFoundError = NotFoundError
    DuplicateError = DuplicateError

    # === Countries ===
    def get_countries(self):
        """ All countries as a DataFrame with columns 'A-2' and 'CountryName' """
        return _countries.get_all()

    def get_country(self, code):
        return _countries.get(code)

    def create_country(self, code, name):
        return _countries.create(code, name)

    def update_country(self, code, name):
        return _countries.update(code, name)

    def delete_country(self, code):
        _countries.delete(code)

    # === Flags ===
    def get_flag_codes(self):
        """ Set of country codes that have a flag image """
        return _flags.list_codes()

    def get_flag(self, code):
        """ Flag image as PNG bytes """
        return _flags.get(code)

    def create_flag(self, code, png_bytes):
        _flags.create(code, png_bytes)

    def update_flag(self, code, png_bytes):
        _flags.update(code, png_bytes)

    def delete_flag(self, code):
        _flags.delete(code)

    # === Arenas ===
    def get_arenas(self):
        """ All arenas as a DataFrame (arena_id, capacity and year are integers) """
        return _arenas.get_all()

    def get_arena(self, arena_id):
        return _arenas.get(arena_id)

    def create_arena(self, arena_name, country, city, capacity, founded):
        """ Adds an arena with the next free arena_id and returns it """
        return _arenas.create(arena_name, country, city, capacity, founded)

    def update_arena(self, arena_id, **changes):
        # e.g. update_arena(12, capacity=18000, city="Leeds")
        return _arenas.update(arena_id, **changes)

    def delete_arena(self, arena_id):
        _arenas.delete(arena_id)