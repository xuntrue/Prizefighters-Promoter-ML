import tkinter as tk

from tkinter import ttk, messagebox
from datetime import date, datetime

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import (
    FighterError, format_full_name,
    CAREER_STAT_FIELDS, PHYSICAL_ATTRIBUTE_FIELDS, PUNCH_ATTRIBUTE_FIELDS,
    TENDENCY_FIELDS, SIGNATURE_TRAIT_GROUPS,
    MIN_ATTRIBUTE, MAX_ATTRIBUTE, ATTRIBUTE_STEP,
    MIN_LEVEL, MAX_LEVEL, MIN_XP, MIN_TENDENCY, MAX_TENDENCY,
    MIN_TRAIT_LEVEL, MAX_TRAIT_LEVEL, MIN_TRAIT_XP, MAX_TRAIT_XP,
    max_xp_for_level, validate_last_6_entry, MAX_LAST_6_ENTRIES,
)
from api.Fights import DATE_FORMAT, FightError


def _fight_display_label(api: PrizefighterAPI, fight_id: str, role: str) -> str:
    fight = api.get_fight(fight_id)
    if fight is None:
        return f"{fight_id} (missing)"
    red = api.get_fighter(fight["red_corner_fighter_id"])
    blue = api.get_fighter(fight["blue_corner_fighter_id"])
    red_name = format_full_name(red["first_name"], red["last_name"], red["nickname"], red["placement"]) if red else "?"
    blue_name = format_full_name(blue["first_name"], blue["last_name"], blue["nickname"], blue["placement"]) if blue else "?"
    return f'[{role}] {fight_id}: {red_name} vs {blue_name} ({fight["weight_limit"]} lbs) -- {fight["status"]}'

class CornerMetaForm(ttk.Frame):
    """ Single corner's full pre-fight form """
    def __init__(self, parent, api: PrizefighterAPI, corner: str, corner_label: str):
        super().__init__(parent)
        self.api = api
        self.corner = corner

        header = ttk.Label(self, text=corner_label, font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", padx=5, pady=(5, 0))
        self.fighter_name_label = ttk.Label(self, text="")
        self.fighter_name_label.pack(anchor="w", padx=5, pady=(0, 5))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._build_profile_tab(notebook)
        self._build_career_stats_tab(notebook)
        self._build_attributes_tab(notebook)
        self._build_skills_tab(notebook)
        self._build_tendencies_tab(notebook)

        ttk.Button(self, text=f"Save {corner_label}", command=self._on_save).pack(
            anchor="w", padx=5, pady=(0, 10))

        self.status_label = ttk.Label(self, text="", foreground="gray", wraplength=380, justify="left")
        self.status_label.pack(anchor="w", padx=5, pady=(0, 5))

        self.current_fight_id = None
        self.current_weight_limit = None

    # ---------- Profile ----------
    def _build_profile_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Profile")

        ttk.Label(tab, text="Weigh-in (lbs):").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.weigh_in_var = tk.StringVar()
        ttk.Entry(tab, textvariable=self.weigh_in_var, width=10).grid(
            row=0, column=1, sticky="w", padx=5, pady=4)
        self.weight_limit_hint = ttk.Label(tab, text="", foreground="gray")
        self.weight_limit_hint.grid(row=0, column=2, sticky="w", padx=5, pady=4)

        ttk.Label(tab, text="Record (W-KO-L-D):").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        record_row = ttk.Frame(tab)
        record_row.grid(row=1, column=1, columnspan=2, sticky="w", padx=5, pady=4)
        self.wins_var = tk.IntVar(value=0)
        self.knockouts_var = tk.IntVar(value=0)
        self.losses_var = tk.IntVar(value=0)
        self.draws_var = tk.IntVar(value=0)
        for label, var in (("W", self.wins_var), ("KO", self.knockouts_var),
                           ("L", self.losses_var), ("D", self.draws_var)):
            ttk.Label(record_row, text=f"{label}:").pack(side="left", padx=(8, 2))
            ttk.Spinbox(record_row, from_=0, to=999, textvariable=var, width=5).pack(side="left")
        ttk.Label(
            tab, text="Pulled from records.csv -- edit here to correct; saving writes the "
                      "correction back to records.csv.",
            foreground="gray", wraplength=380, justify="left",
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(0, 8))

        ttk.Label(tab, text=f"Last 6 (most recent first, max {MAX_LAST_6_ENTRIES}):").grid(
            row=3, column=0, columnspan=3, sticky="w", padx=5, pady=(4, 0))
        ttk.Label(
            tab, text='One per line, e.g. "W-TKO(8)". Methods: KO, TKO, UD, SD, MD.',
            foreground="gray",
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=5)
        self.last_6_text = tk.Text(tab, width=30, height=6)
        self.last_6_text.grid(row=5, column=0, columnspan=3, sticky="w", padx=5, pady=(2, 5))

    def _get_last_6(self) -> list:
        raw = self.last_6_text.get("1.0", "end").strip()
        if not raw:
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _set_last_6(self, entries: list):
        self.last_6_text.delete("1.0", "end")
        self.last_6_text.insert("1.0", "\n".join(entries))

    # ---------- Career Stats ----------
    def _build_career_stats_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Career Stats")

        self.career_stat_vars = {}
        for row, (key, label) in enumerate(CAREER_STAT_FIELDS):
            ttk.Label(tab, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=5, pady=4)
            var = tk.IntVar(value=0)
            ttk.Spinbox(tab, from_=0, to=10_000_000, textvariable=var, width=10).grid(
                row=row, column=1, sticky="w", padx=5, pady=4)
            self.career_stat_vars[key] = var

    # ---------- Attributes ----------
    def _build_attributes_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Attributes")

        self.attribute_vars = {}
        row = 0
        ttk.Label(tab, text="Physical", font=("TkDefaultFont", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 2))
        row += 1
        for key, label in PHYSICAL_ATTRIBUTE_FIELDS:
            ttk.Label(tab, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
            var = tk.DoubleVar(value=5.0)
            ttk.Spinbox(tab, from_=MIN_ATTRIBUTE, to=MAX_ATTRIBUTE, increment=ATTRIBUTE_STEP,
                       textvariable=var, width=6, format="%.1f").grid(
                row=row, column=1, sticky="w", padx=5, pady=3)
            self.attribute_vars[key] = var
            row += 1

        ttk.Label(tab, text="Punching", font=("TkDefaultFont", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(10, 2))
        row += 1
        for key, label in PUNCH_ATTRIBUTE_FIELDS:
            ttk.Label(tab, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=5, pady=3)
            var = tk.DoubleVar(value=5.0)
            ttk.Spinbox(tab, from_=MIN_ATTRIBUTE, to=MAX_ATTRIBUTE, increment=ATTRIBUTE_STEP,
                       textvariable=var, width=6, format="%.1f").grid(
                row=row, column=1, sticky="w", padx=5, pady=3)
            self.attribute_vars[key] = var
            row += 1

    # ---------- Skills ----------
    def _build_skills_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Skills")
 
        ttk.Label(tab, text="Experience Level:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.level_var = tk.IntVar(value=MIN_LEVEL)
        level_spin = ttk.Spinbox(tab, from_=MIN_LEVEL, to=MAX_LEVEL, textvariable=self.level_var,
                                 width=5, command=self._on_level_changed)
        level_spin.grid(row=0, column=1, sticky="w", padx=5, pady=4)
 
        ttk.Label(tab, text="XP:").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        self.xp_var = tk.IntVar(value=MIN_XP)
        self.xp_spin = ttk.Spinbox(tab, from_=MIN_XP, to=max_xp_for_level(MIN_LEVEL),
                                   textvariable=self.xp_var, width=6)
        self.xp_spin.grid(row=1, column=1, sticky="w", padx=5, pady=4)
        self.xp_max_label = ttk.Label(tab, text=f"/ {max_xp_for_level(MIN_LEVEL)}", foreground="gray")
        self.xp_max_label.grid(row=1, column=2, sticky="w", padx=5, pady=4)
 
        ttk.Label(tab, text="Signature Traits", font=("TkDefaultFont", 9, "bold")).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=5, pady=(12, 4))
 
        self.trait_vars = {}
        for i, (group, options) in enumerate(SIGNATURE_TRAIT_GROUPS.items()):
            ttk.Label(tab, text=f"Group {i + 1}:").grid(row=3 + i, column=0, sticky="w", padx=5, pady=3)
 
            row_frame = ttk.Frame(tab)
            row_frame.grid(row=3 + i, column=1, columnspan=2, sticky="w", padx=5, pady=3)
 
            name_var = tk.StringVar(value="None")
            ttk.Combobox(row_frame, textvariable=name_var, values=["None"] + options,
                        state="readonly", width=18).pack(side="left")
 
            ttk.Label(row_frame, text="Lv:").pack(side="left", padx=(8, 2))
            level_var = tk.IntVar(value=MIN_TRAIT_LEVEL)
            ttk.Spinbox(row_frame, from_=MIN_TRAIT_LEVEL, to=MAX_TRAIT_LEVEL,
                       textvariable=level_var, width=3).pack(side="left")
 
            ttk.Label(row_frame, text="XP:").pack(side="left", padx=(8, 2))
            xp_var = tk.IntVar(value=MIN_TRAIT_XP)
            ttk.Spinbox(row_frame, from_=MIN_TRAIT_XP, to=MAX_TRAIT_XP,
                       textvariable=xp_var, width=3).pack(side="left")
 
            self.trait_vars[group] = {"name": name_var, "level": level_var, "xp": xp_var}
 
    def _on_level_changed(self):
        max_xp = max_xp_for_level(self.level_var.get())
        self.xp_spin.config(to=max_xp)
        self.xp_max_label.config(text=f"/ {max_xp}")
        if self.xp_var.get() > max_xp:
            self.xp_var.set(max_xp)

    # ---------- Tendencies ----------
    def _build_tendencies_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Tendencies")

        self.tendency_vars = {}
        for row, (key, label_a, label_b) in enumerate(TENDENCY_FIELDS):
            ttk.Label(tab, text=label_a, width=22, anchor="e").grid(
                row=row, column=0, sticky="e", padx=(5, 2), pady=3)
            var = tk.IntVar(value=50)
            ttk.Scale(tab, from_=MIN_TENDENCY, to=MAX_TENDENCY, orient="horizontal",
                     variable=var, length=140).grid(row=row, column=1, padx=2, pady=3)
            ttk.Label(tab, text=label_b, width=22, anchor="w").grid(
                row=row, column=2, sticky="w", padx=(2, 5), pady=3)
            value_label = ttk.Label(tab, textvariable=var, width=4)
            value_label.grid(row=row, column=3, padx=(2, 5), pady=3)
            self.tendency_vars[key] = var

    # ---------- Load / gather ----------
    def load_fight(self, fight_id: str, fighter_label: str, weight_limit: int):
        self.current_fight_id = fight_id
        self.current_weight_limit = weight_limit
        self.fighter_name_label.config(text=fighter_label)
        self.weight_limit_hint.config(text=f"(limit: {weight_limit} lbs)")
        self.status_label.config(text="")

        corner_key = "red_corner" if self.corner == "red_corner" else "blue_corner"
        default_meta = self.api.get_default_meta_for_fighter(fight_id, corner_key)
        self._apply_meta(default_meta)

    def _apply_meta(self, meta: dict):
        profile = meta["profile"]
        self.weigh_in_var.set(str(profile["weigh_in"]))
        self.wins_var.set(profile["record"]["wins"])
        self.knockouts_var.set(profile["record"]["knockouts"])
        self.losses_var.set(profile["record"]["losses"])
        self.draws_var.set(profile["record"]["draws"])
        self._set_last_6(profile["last_6"])

        for key, var in self.career_stat_vars.items():
            var.set(meta["career_stats"][key])

        for key, var in self.attribute_vars.items():
            var.set(meta["attributes"][key])

        self.level_var.set(meta["skills"]["experience"]["level"])
        self._on_level_changed()
        self.xp_var.set(meta["skills"]["experience"]["xp"])
 
        for group, trait_vars in self.trait_vars.items():
            pick = meta["skills"]["signature_traits"].get(group)
            if pick:
                trait_vars["name"].set(pick["name"])
                trait_vars["level"].set(pick["level"])
                trait_vars["xp"].set(pick["xp"])
            else:
                trait_vars["name"].set("None")
                trait_vars["level"].set(MIN_TRAIT_LEVEL)
                trait_vars["xp"].set(MIN_TRAIT_XP)

        for key, var in self.tendency_vars.items():
            var.set(meta["tendencies"][key])

    def _gather_meta(self) -> dict:
        try:
            weigh_in = int(self.weigh_in_var.get())
        except ValueError:
            raise FighterError("Weigh-in must be a whole number.")

        return {
            "profile": {
                "weigh_in": weigh_in,
                "record": {
                    "wins": self.wins_var.get(),
                    "knockouts": self.knockouts_var.get(),
                    "losses": self.losses_var.get(),
                    "draws": self.draws_var.get(),
                },
                "last_6": [validate_last_6_entry(e) for e in self._get_last_6()],
            },
            "career_stats": {key: var.get() for key, var in self.career_stat_vars.items()},
            "attributes": {key: round(float(var.get()), 1) for key, var in self.attribute_vars.items()},
            "skills": {
                "experience": {"level": self.level_var.get(), "xp": self.xp_var.get()},
                "signature_traits": {
                    group: (
                        None if trait_vars["name"].get() == "None"
                        else {
                            "name": trait_vars["name"].get(),
                            "level": trait_vars["level"].get(),
                            "xp": trait_vars["xp"].get(),
                        }
                    )
                    for group, trait_vars in self.trait_vars.items()
                },
            },
            "tendencies": {key: var.get() for key, var in self.tendency_vars.items()},
        }

    # ---------- Save ----------
    def _on_save(self):
        if self.current_fight_id is None:
            messagebox.showerror("No Fight Selected", "Select a bout before saving.")
            return

        try:
            meta = self._gather_meta()
            self.api.save_fight_meta(self.current_fight_id, self.corner, meta)
        except (FighterError, FightError) as e:
            messagebox.showerror("Could Not Save", str(e))
            return

        fight = self.api.get_fight(self.current_fight_id)
        messagebox.showinfo("Saved", f"{self.corner.replace('_', ' ').title()} meta saved.")
        self.status_label.config(text=f"Saved. Fight status is now: {fight['status']}.")

class RecordFightPrefightTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api
        self._event_options = []   # list of (event_id, label)
        self._bout_options = []    # list of (fight_id, role_label)

        self._build_reference_date()
        self._build_selectors()
        self._build_corner_forms()

        self.refresh_reference_data()

    # ---------- Construction ----------
    def _build_reference_date(self):
        date_frame = ttk.LabelFrame(self, text="Game's Current Date")
        date_frame.pack(fill="x", padx=10, pady=(10, 5))

        today = date.today()
        self.ref_day_var = tk.StringVar(value=str(today.day))
        self.ref_month_var = tk.StringVar(value=str(today.month))
        self.ref_year_var = tk.StringVar(value=str(today.year))

        ttk.Label(date_frame, text="Day:").pack(side="left", padx=(5, 2))
        ttk.Spinbox(date_frame, from_=1, to=31, textvariable=self.ref_day_var, width=4,
                   command=self._refresh_event_list).pack(side="left")
        ttk.Label(date_frame, text="Month:").pack(side="left", padx=(10, 2))
        ttk.Spinbox(date_frame, from_=1, to=12, textvariable=self.ref_month_var, width=4,
                   command=self._refresh_event_list).pack(side="left")
        ttk.Label(date_frame, text="Year:").pack(side="left", padx=(10, 2))
        ttk.Spinbox(date_frame, from_=1900, to=2100, textvariable=self.ref_year_var, width=6,
                   command=self._refresh_event_list).pack(side="left")

        for var in (self.ref_day_var, self.ref_month_var, self.ref_year_var):
            var.trace_add("write", lambda *args: self._refresh_event_list())

    def _build_selectors(self):
        box = ttk.LabelFrame(self, text="Select a Bout")
        box.pack(fill="x", padx=10, pady=5)

        ttk.Label(box, text="Event:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(box, textvariable=self.event_var, state="readonly", width=50)
        self.event_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.event_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_event_selected())

        ttk.Label(box, text="Bout:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.bout_var = tk.StringVar()
        self.bout_combo = ttk.Combobox(box, textvariable=self.bout_var, state="readonly", width=50)
        self.bout_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.bout_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_bout_selected())

    def _build_corner_forms(self):
        forms_area = ttk.Frame(self)
        forms_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.red_form = CornerMetaForm(forms_area, self.api, "red_corner", "Red Corner")
        self.red_form.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.blue_form = CornerMetaForm(forms_area, self.api, "blue_corner", "Blue Corner")
        self.blue_form.pack(side="left", fill="both", expand=True, padx=(5, 0))

    # ---------- Lifecycle ----------
    def on_tab_shown(self):
        self.refresh_reference_data()

    def refresh_reference_data(self):
        self._refresh_event_list()

    # ---------- Event / bout selection ----------
    def _refresh_event_list(self):
        try:
            ref_date = date(int(self.ref_year_var.get()), int(self.ref_month_var.get()),
                            int(self.ref_day_var.get()))
        except (ValueError, tk.TclError):
            return

        events = [
            e for e in self.api.get_events()
            if self._parse_date(e["date"]) and self._parse_date(e["date"]) >= ref_date
        ]
        events.sort(key=lambda e: e["event_id"]) # Sort by eventID

        self._event_options = [
            (e["event_id"], f'{e["date"]} -- {e["headliner"]}') #(Event #{e["event_id"]})')
            for e in events
        ]
        self.event_combo["values"] = [label for _eid, label in self._event_options]
        self.event_var.set("")
        self.bout_combo["values"] = []
        self.bout_var.set("")

    @staticmethod
    def _parse_date(date_str: str):
        try:
            return datetime.strptime(date_str, DATE_FORMAT).date()
        except (ValueError, TypeError):
            return None

    def _selected_event_id(self):
        label = self.event_var.get()
        for event_id, option_label in self._event_options:
            if option_label == label:
                return event_id
        return None

    def _on_event_selected(self):
        event_id = self._selected_event_id()
        if event_id is None:
            return
        event = self.api.get_event(event_id)
        if event is None:
            return

        bouts = (
            [(event["main_event_fight_id"], "Main Event")]
            + [(fid, "Co-Main") for fid in event["co_main_fight_ids"]]
            + [(fid, "Undercard") for fid in event["undercard_fight_ids"]]
        )
        self._bout_options = [
            (fight_id, _fight_display_label(self.api, fight_id, role)) for fight_id, role in bouts
        ]
        self.bout_combo["values"] = [label for _fid, label in self._bout_options]
        self.bout_var.set("")

    def _selected_fight_id(self):
        label = self.bout_var.get()
        for fight_id, option_label in self._bout_options:
            if option_label == label:
                return fight_id
        return None

    def _on_bout_selected(self):
        fight_id = self._selected_fight_id()
        if fight_id is None:
            return

        fight = self.api.get_fight(fight_id)
        if fight is None:
            return

        red = self.api.get_fighter(fight["red_corner_fighter_id"])
        blue = self.api.get_fighter(fight["blue_corner_fighter_id"])
        red_label = format_full_name(red["first_name"], red["last_name"], red["nickname"], red["placement"]) if red else "?"
        blue_label = format_full_name(blue["first_name"], blue["last_name"], blue["nickname"], blue["placement"]) if blue else "?"

        self.red_form.load_fight(fight_id, red_label, fight["weight_limit"])
        self.blue_form.load_fight(fight_id, blue_label, fight["weight_limit"])