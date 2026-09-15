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


class FighterFormFrame(ttk.Frame):
    """A reusable block of fighter fields. Call get_values()/set_values()/clear()
    from the screen that embeds this frame."""

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

        ttk.Label(self, text="First Name:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.first_name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.first_name_var, width=25).grid(
            row=row, column=1, sticky="w", padx=5, pady=4
        )
        row += 1

        ttk.Label(self, text="Last Name:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.last_name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.last_name_var, width=25).grid(
            row=row, column=1, sticky="w", padx=5, pady=4
        )
        row += 1

        ttk.Label(self, text="Nickname:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.nickname_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.nickname_var, width=25).grid(
            row=row, column=1, sticky="w", padx=5, pady=4
        )
        row += 1

        ttk.Label(self, text="Nickname Placement:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.placement_var = tk.StringVar(value="None")
        ttk.Combobox(
            self, textvariable=self.placement_var, values=PLACEMENTS, state="readonly", width=22
        ).grid(row=row, column=1, sticky="w", padx=5, pady=4)
        row += 1

        ttk.Label(self, text="Hometown:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.hometown_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.hometown_var, width=25).grid(
            row=row, column=1, sticky="w", padx=5, pady=4
        )
        row += 1

        ttk.Label(self, text="Country:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.country_var = tk.StringVar()
        self.country_combo = ttk.Combobox(self, textvariable=self.country_var, state="readonly", width=30)
        self.country_combo.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        row += 1

        ttk.Label(self, text="Birthdate (dd-mm-yyyy):").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.birthdate_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.birthdate_var, width=15).grid(
            row=row, column=1, sticky="w", padx=5, pady=4
        )
        row += 1

        ttk.Label(self, text="Weight Class:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.weight_class_var = tk.StringVar()
        self.weight_class_combo = ttk.Combobox(
            self, textvariable=self.weight_class_var, state="readonly", width=30
        )
        self.weight_class_combo.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        row += 1

        ttk.Label(self, text=f"Reach (in, {MIN_REACH}-{MAX_REACH}):").grid(
            row=row, column=0, sticky="w", padx=5, pady=4
        )
        self.reach_var = tk.StringVar(value=str(MIN_REACH))
        ttk.Spinbox(
            self, from_=MIN_REACH, to=MAX_REACH, textvariable=self.reach_var, width=5
        ).grid(row=row, column=1, sticky="w", padx=5, pady=4)
        row += 1

        ttk.Label(self, text="Stance:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        stance_frame = ttk.Frame(self)
        stance_frame.grid(row=row, column=1, sticky="w", padx=5, pady=4)
        self.stance_var = tk.StringVar(value="Orthodox")
        for stance_name in STANCE_TO_INT:
            ttk.Radiobutton(
                stance_frame, text=stance_name, variable=self.stance_var, value=stance_name
            ).pack(side="left", padx=(0, 10))
        row += 1

        ttk.Label(self, text="Style:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
        self.style_var = tk.StringVar(value="In Fighter")
        ttk.Combobox(
            self, textvariable=self.style_var, values=list(STYLE_TO_INT.keys()), state="readonly", width=22
        ).grid(row=row, column=1, sticky="w", padx=5, pady=4)

    # ---------- Live-update hook ----------

    def bind_change(self, callback):
        """Call `callback()` (no arguments) whenever any field in this form
        changes. Used by add_fighter.py to keep its preview pane in sync."""
        watched_vars = (
            self.first_name_var, self.last_name_var, self.nickname_var,
            self.placement_var, self.hometown_var, self.country_var,
            self.birthdate_var, self.weight_class_var, self.reach_var,
            self.stance_var, self.style_var,
        )
        for var in watched_vars:
            var.trace_add("write", lambda *_args: callback())

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
            self.country_var.set(f"{country['a2']} - {country['country_name']}")

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
