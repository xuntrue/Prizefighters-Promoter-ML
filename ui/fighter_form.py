import calendar
import random
import tkinter as tk
from tkinter import ttk

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import (
    PLACEMENTS,
    STANCE_TO_INT,
    INT_TO_STANCE,
    STYLE_TO_INT,
    INT_TO_STYLE,
    MIN_REACH,
    MAX_REACH,
)

MONTHS = [
    "JAN", "FEB", "MAR", "APR",
    "MAY", "JUN", "JUL", "AUG",
    "SEP", "OCT", "NOV", "DEC"
]

class FighterFormFrame(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api

        # Cached so combobox selections can be mapped back to codes/ids.
        self._country_options = []   # list of (a2, country_name)
        self._weight_class_options = []  # list of (weight_limit, weight_class)

        self._build_fields()
        self.refresh_reference_data()

    # ---------- Construction ----------
    def _build_fields(self):
        row = 0

        # --- Row 0: First + Last name share one cell ---
        ttk.Label(self, text="Name (First / Last):").grid( row=row, column=0, sticky="w", padx=5, pady=4)
        name_row = ttk.Frame(self)
        name_row.grid(row=row, column=1, sticky="w", padx=5, pady=4)

        self.first_name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self.first_name_var, width=14).pack(side="left")

        self.last_name_var = tk.StringVar()
        ttk.Entry(name_row, textvariable=self.last_name_var, width=14).pack(side="left", padx=(6, 0))
        row += 1

        # --- Row 1: Nickname + its placement share one cell ---
        ttk.Label(self, text="Nickname / Placement:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        nickname_row = ttk.Frame(self)
        nickname_row.grid(row=row, column=1, sticky="w", padx=5, pady=4)

        self.nickname_var = tk.StringVar()
        ttk.Entry(nickname_row, textvariable=self.nickname_var, width=16).pack(side="left")

        self.placement_var = tk.StringVar(value="None")
        ttk.Combobox(nickname_row, textvariable=self.placement_var, values=PLACEMENTS, state="readonly", width=8).pack(side="left", padx=(6, 0))
        row += 1

        # --- Row 2: Hometown ---
        ttk.Label(self, text="Hometown:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.hometown_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.hometown_var, width=25).grid(
            row=row, column=1, sticky="w", padx=5, pady=4
        )
        row += 1

        # --- Row 3: Country ---
        ttk.Label(self, text="Country:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.country_var = tk.StringVar()
        self.country_combo = ttk.Combobox(self, textvariable=self.country_var, state="readonly", width=30)
        self.country_combo.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        row += 1

        # --- Row 4a: Birthdate ---
        ttk.Label(self, text="Birthdate (dd-mm-yyyy):").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        birthdate_frame = ttk.Frame(self)
        birthdate_frame.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        
        self.birth_day_var = tk.StringVar() # Day Entry
        self.day_entry = ttk.Entry(birthdate_frame, textvariable=self.birth_day_var, width=5).grid(
            row=0, column=0, padx=(0, 5)
        )

        self.birth_month_var = tk.StringVar() # Month Combobox
        self.month_combo = ttk.Combobox(birthdate_frame, textvariable=self.birth_month_var, values=MONTHS, state="readonly", width=12).grid(
            row=0, column=1, padx=5
        )

        self.birth_year_var = tk.StringVar() # Year Entry
        self.year_entry = ttk.Entry(birthdate_frame, textvariable=self.birth_year_var, width=8).grid(
            row=0, column=2, padx=(5, 0)
        )

        self.birthdate_var = tk.StringVar() # Unified birthdate variable (dd-mm-yyyy)

        # Update the combined date whenever an input changes
        self.birth_day_var.trace_add("write", self._update_birthdate)
        self.birth_month_var.trace_add("write", self._update_birthdate)
        self.birth_year_var.trace_add("write", self._update_birthdate)

        row += 1

        # --- Row 4b: Random Day ---
        ttk.Button(self, text="Random Day", command=self._random_birth_day).grid(
            row=row, column=1, sticky="w", padx=5, pady=4
        )
        row += 1

        # --- Row 5: Weight Class ---
        ttk.Label(self, text="Weight Class:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.weight_class_var = tk.StringVar()
        self.weight_class_combo = ttk.Combobox(
            self, textvariable=self.weight_class_var, state="readonly", width=30
        )
        self.weight_class_combo.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        row += 1

        # --- Row 6: Reach ---
        ttk.Label(self, text=f"Reach (in, {MIN_REACH}-{MAX_REACH}):").grid(
            row=row, column=0, sticky="w", padx=5, pady=4
        )
        self.reach_var = tk.StringVar(value=str(MIN_REACH))
        ttk.Spinbox(
            self, from_=MIN_REACH, to=MAX_REACH, textvariable=self.reach_var, width=5
        ).grid(row=row, column=1, sticky="w", padx=5, pady=4)
        row += 1

        # --- Row 7: Stance ---
        ttk.Label(self, text="Stance:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        stance_frame = ttk.Frame(self)
        stance_frame.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        self.stance_var = tk.StringVar(value="Orthodox")
        for stance_name in STANCE_TO_INT:
            ttk.Radiobutton(
                stance_frame, text=stance_name, variable=self.stance_var, value=stance_name
            ).pack(side="left", padx=(0, 10))
        row += 1

        # --- Row 8: Style ---
        ttk.Label(self, text="Style:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.style_var = tk.StringVar(value="In Fighter")
        ttk.Combobox(
            self, textvariable=self.style_var, values=list(STYLE_TO_INT.keys()), state="readonly", width=22
        ).grid(row=row, column=1, sticky="w", padx=5, pady=4)

    # ---------- Live-update hook ----------
    def bind_change(self, callback):
        """Call `callback()` (no arguments) whenever any field in this form changes """
        watched_vars = (
            self.first_name_var, self.last_name_var, self.nickname_var,
            self.placement_var, self.hometown_var, self.country_var,
            self.birthdate_var, self.weight_class_var, self.reach_var,
            self.stance_var, self.style_var,
        )
        for var in watched_vars:
            var.trace_add("write", lambda *_args: callback())

    def _update_birthdate(self, *_):
        """ Combine the day, month, and year into dd-mm-yyyy """
        day = self.birth_day_var.get().strip()
        month = self.birth_month_var.get()
        year = self.birth_year_var.get().strip()

        # Clear the combined date until all fields are populated
        if not day or not month or not year:
            self.birthdate_var.set("")
            return

        try:
            day = int(day)
            year = int(year)
            month_number = MONTHS.index(month) + 1
            # Validate the date
            if not 1 <= day <= calendar.monthrange(year, month_number)[1]:
                self.birthdate_var.set("")
                return

            self.birthdate_var.set(f"{day:02d}-{month_number:02d}-{year:04d}")

        except (ValueError, IndexError):
            self.birthdate_var.set("")

    def _random_birth_day(self):
        """Generate a random valid day for the selected month and year """
        month = self.birth_month_var.get()
        year = self.birth_year_var.get().strip()
        
        if not month or not year:
            return
        try:
            year = int(year)
            month_number = MONTHS.index(month) + 1    
            days_in_month = calendar.monthrange(year, month_number)[1] # Get number of days in the selected month
            random_day = random.randint(1, days_in_month) # Generate random day
            self.birth_day_var.set(str(random_day))
        except (ValueError, IndexError):
            return

    # ---------- Reference data (countries / weight classes) ----------
    def refresh_reference_data(self):
        """Reload country and weight-class options from API """
        self._country_options = [(c["country_name"], c["a2"]) for c in self.api.get_countries()]
        self.country_combo["values"] = [f"[{a2}] {name}" for name, a2 in self._country_options]

        self._weight_class_options = [
            (wc["weight_limit"], wc["weight_class"]) for wc in self.api.get_weight_classes()
        ]
        self.weight_class_combo["values"] = [
            f"{limit} - {name}" for limit, name in self._weight_class_options
        ]

    # ---------- Reading / writing values ----------
    def get_raw_values(self) -> dict:
        """Return the form's values as the raw strings/ints Fighter.add()/update()
        expect. Does NOT validate -- that's api.Fighter's job."""
        country_a2 = self.country_var.get()[1:3] if self.country_var.get() else ""

        weight_class_text = self.weight_class_var.get()
        weightclass = None
        if weight_class_text:
            try:
                weightclass = int(weight_class_text.split(" - ")[0].strip())
            except ValueError:
                weightclass = None

        return {
            "first_name": self.first_name_var.get(),
            "last_name": self.last_name_var.get(),
            "nickname": self.nickname_var.get(),
            "placement": self.placement_var.get(),
            "hometown": self.hometown_var.get(),
            "country": country_a2,
            "birthdate": self.birthdate_var.get(),
            "weightclass": weightclass,
            "reach": int(self.reach_var.get()) if str(self.reach_var.get()).isdigit() else None,
            "stance": STANCE_TO_INT.get(self.stance_var.get()),
            "style": STYLE_TO_INT.get(self.style_var.get()),
        }

    def set_values(self, fighter: dict):
        """Populate the form from a fighter dict as returned by PrizefighterAPI
        (i.e. using the internal snake_case / int-coded representation)."""
        self.first_name_var.set(fighter["first_name"])
        self.last_name_var.set(fighter["last_name"])
        self.nickname_var.set(fighter["nickname"])
        self.placement_var.set(fighter["placement"])
        self.hometown_var.set(fighter["hometown"])

        country = self.api.countries.get_by_code(fighter["country"])
        if country:
            self.country_var.set(f"[{country['a2']}] {country['country_name']}")

        self.birthdate_var.set(fighter["birthdate"])

        weight_match = next(
            (wc for wc in self._weight_class_options if wc[0] == fighter["weightclass"]), None
        )
        if weight_match:
            self.weight_class_var.set(f"{weight_match[0]} - {weight_match[1]}")

        self.reach_var.set(str(fighter["reach"]))
        self.stance_var.set(INT_TO_STANCE.get(fighter["stance"], "Orthodox"))
        self.style_var.set(INT_TO_STYLE.get(fighter["style"], "In Fighter"))

    def clear(self):
        self.first_name_var.set("")
        self.last_name_var.set("")
        self.nickname_var.set("")
        self.placement_var.set("None")
        self.hometown_var.set("")
        self.country_var.set("")
        self.birthdate_var.set("")
        self.weight_class_var.set("")
        self.reach_var.set(str(MIN_REACH))
        self.stance_var.set("Orthodox")
        self.style_var.set("In Fighter")