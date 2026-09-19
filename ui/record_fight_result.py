"""
record_fight_result.py

Tab for recording a fight's "result" block on fight day: cornering
gyms, round-by-round punch stats, judges' scorecards, the stoppage (if
any), the outcome, and each corner's post-fight changes.

Workflow: pick a bout the same way as Pre-Fight Meta (game date filters
the event list, then pick a bout on that event's card) -- but only
fights already in Meta status are offered, since a result can't be
recorded before pre-fight meta exists for both corners. Set how the
fight ended, click "Build Rounds & Scorecards" to lay out the grids for
however many rounds actually happened, fill everything in, then Save.

This screen deliberately doesn't try to be clever: nothing is
auto-computed except "power" (which the user never sees a field for --
it's derived silently), and nothing is pre-filled from a "sensible
default" the way Pre-Fight Meta's carry-forward is. Every number here
gets typed in by hand.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import format_full_name
from api.Fights import (
    DATE_FORMAT, FightError, STATUS_META,
    CORNERS, JUDGES, PUNCH_TYPE_FIELDS, TARGET_FIELDS, COUNTER_FIELD,
    STOPPAGE_METHODS, DECISION_METHODS, OUTCOME_METHODS,
    MIN_ROUND_SCORE, MAX_ROUND_SCORE,
    TENDENCY_CHANGE_FIELDS, MIN_TENDENCY_CHANGE, MAX_TENDENCY_CHANGE,
)
from api.Gyms import GymError

CORNER_LABELS = {"red_corner": "Red Corner", "blue_corner": "Blue Corner"}

# Display label for each punch-stat row, in the order they're shown.
PUNCH_STAT_ROWS = [(key, key.replace("_", " ").title()) for key in PUNCH_TYPE_FIELDS] + [
    ("head", "Head"), ("body", "Body"), (COUNTER_FIELD, "Counter"),
]

DECISION = "Decision"
STOPPED = "Stopped (KO/TKO)"
DRAW_LABEL = "Draw"


class HScrollFrame(ttk.Frame):
    """A frame with a horizontal scrollbar -- used for the scorecard and
    punch-stat grids, which get wide fast once rounds are added."""

    def __init__(self, parent, height=180):
        super().__init__(parent)
        canvas = tk.Canvas(self, height=height, highlightthickness=0)
        hbar = ttk.Scrollbar(self, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=hbar.set)

        self.inner = ttk.Frame(canvas)
        self.inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.inner, anchor="nw")

        canvas.pack(side="top", fill="both", expand=True)
        hbar.pack(side="bottom", fill="x")


def _int_entry(parent, width=4, default="0"):
    var = tk.StringVar(value=default)
    entry = ttk.Entry(parent, textvariable=var, width=width)
    return entry, var


class RecordFightResultTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api

        self.current_fight = None       # the selected fight's index row
        self.current_fight_id = None
        self._event_options = []
        self._bout_options = []
        self._gym_options = []          # list of (gym_id_or_None, label)

        self.scorecard_vars = {}        # [judge][corner] -> list[StringVar] (len = sanctioned rounds)
        self.scorecard_entries = {}     # same shape, holds the Entry widgets (for enable/disable)
        self.punch_vars = {}            # [corner][round_index][field] -> {"thrown": var, "landed": var}
        self.knocked_down_vars = {}     # [corner][round_index] -> var

        self._build_reference_date()
        self._build_selectors()
        self._build_gyms_and_ending()
        self._build_scorecards_area()
        self._build_punch_stats_area()
        self._build_outcome_and_post_fight()

        self.refresh_reference_data()

    # ---------- Top: reference date + bout selection ----------

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
        box = ttk.LabelFrame(self, text="Select a Bout (only bouts with completed Pre-Fight Meta are shown)")
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

    # ---------- Gyms + how the fight ended ----------

    def _build_gyms_and_ending(self):
        box = ttk.LabelFrame(self, text="Corners & How It Ended")
        box.pack(fill="x", padx=10, pady=5)

        ttk.Label(box, text="Red Corner Gym:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.red_gym_var = tk.StringVar()
        self.red_gym_combo = ttk.Combobox(box, textvariable=self.red_gym_var, state="readonly", width=25)
        self.red_gym_combo.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="Blue Corner Gym:").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=4)
        self.blue_gym_var = tk.StringVar()
        self.blue_gym_combo = ttk.Combobox(box, textvariable=self.blue_gym_var, state="readonly", width=25)
        self.blue_gym_combo.grid(row=0, column=3, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="Fight ended by:").grid(row=1, column=0, sticky="w", padx=5, pady=(10, 4))
        self.end_type_var = tk.StringVar(value=DECISION)
        end_type_combo = ttk.Combobox(box, textvariable=self.end_type_var, state="readonly",
                                      values=[DECISION, STOPPED], width=20)
        end_type_combo.grid(row=1, column=1, sticky="w", padx=5, pady=(10, 4))
        end_type_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_end_type_changed())

        self.stoppage_frame = ttk.Frame(box)
        self.stoppage_frame.grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=4)

        ttk.Label(self.stoppage_frame, text="Round:").pack(side="left", padx=(0, 2))
        self.stoppage_round_var = tk.StringVar(value="1")
        self.stoppage_round_spin = ttk.Spinbox(self.stoppage_frame, from_=1, to=12,
                                               textvariable=self.stoppage_round_var, width=4)
        self.stoppage_round_spin.pack(side="left", padx=(0, 10))

        ttk.Label(self.stoppage_frame, text="Losing Corner:").pack(side="left", padx=(0, 2))
        self.losing_corner_var = tk.StringVar(value="Red")
        ttk.Combobox(self.stoppage_frame, textvariable=self.losing_corner_var, state="readonly",
                    values=["Red", "Blue"], width=6).pack(side="left", padx=(0, 10))

        ttk.Label(self.stoppage_frame, text="Method:").pack(side="left", padx=(0, 2))
        self.stoppage_method_var = tk.StringVar(value=STOPPAGE_METHODS[0])
        ttk.Combobox(self.stoppage_frame, textvariable=self.stoppage_method_var, state="readonly",
                    values=list(STOPPAGE_METHODS), width=6).pack(side="left", padx=(0, 10))

        ttk.Label(self.stoppage_frame, text="Time:").pack(side="left", padx=(0, 2))
        self.time_min_var = tk.StringVar(value="0")
        ttk.Entry(self.stoppage_frame, textvariable=self.time_min_var, width=3).pack(side="left")
        ttk.Label(self.stoppage_frame, text="'").pack(side="left")
        self.time_sec_var = tk.StringVar(value="0")
        ttk.Entry(self.stoppage_frame, textvariable=self.time_sec_var, width=3).pack(side="left")
        ttk.Label(self.stoppage_frame, text='"').pack(side="left")
        self.time_centisec_var = tk.StringVar(value="0")
        ttk.Entry(self.stoppage_frame, textvariable=self.time_centisec_var, width=3).pack(side="left")

        self._on_end_type_changed()  # hide stoppage fields initially (Decision is the default)

        ttk.Button(box, text="Build Rounds & Scorecards", command=self._build_rounds_and_scorecards).grid(
            row=3, column=0, columnspan=4, sticky="w", padx=5, pady=(10, 5))

        self.build_status_label = ttk.Label(box, text="", foreground="gray")
        self.build_status_label.grid(row=4, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

    def _on_end_type_changed(self):
        state = "normal" if self.end_type_var.get() == STOPPED else "disabled"
        for child in self.stoppage_frame.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass  # plain Labels don't have a state option

    # ---------- Scorecards ----------
    def _build_scorecards_area(self):
        frame = ttk.LabelFrame(self, text="Judges' Scorecards")
        frame.pack(fill="x", padx=10, pady=5)
        self.scorecards_scroll = HScrollFrame(frame, height=160)
        self.scorecards_scroll.pack(fill="x", padx=5, pady=5)

    # ---------- Punch stats ----------
    def _build_punch_stats_area(self):
        frame = ttk.LabelFrame(self, text="Round-by-Round Punch Stats (Thrown / Landed)")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.punch_notebook = ttk.Notebook(frame)
        self.punch_notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.punch_scrolls = {}
        for corner in CORNERS:
            scroll = HScrollFrame(self.punch_notebook, height=320)
            self.punch_notebook.add(scroll, text=CORNER_LABELS[corner])
            self.punch_scrolls[corner] = scroll

    # ---------- Outcome + post-fight ----------
    def _build_outcome_and_post_fight(self):
        frame = ttk.LabelFrame(self, text="Outcome & Post-Fight")
        frame.pack(fill="x", padx=10, pady=(5, 10))

        outcome_row = ttk.Frame(frame)
        outcome_row.pack(fill="x", padx=5, pady=5)

        ttk.Label(outcome_row, text="Winner:").pack(side="left", padx=(0, 2))
        self.winner_var = tk.StringVar()
        self.winner_combo = ttk.Combobox(outcome_row, textvariable=self.winner_var,
                                         state="readonly", width=25)
        self.winner_combo.pack(side="left", padx=(0, 15))

        ttk.Label(outcome_row, text="Method:").pack(side="left", padx=(0, 2))
        self.outcome_method_var = tk.StringVar(value=OUTCOME_METHODS[0])
        ttk.Combobox(outcome_row, textvariable=self.outcome_method_var, state="readonly",
                    values=list(OUTCOME_METHODS), width=6).pack(side="left")

        post_fight_row = ttk.Frame(frame)
        post_fight_row.pack(fill="x", padx=5, pady=(10, 5))

        self.post_fight_vars = {}
        for corner in CORNERS:
            corner_box = ttk.LabelFrame(post_fight_row, text=CORNER_LABELS[corner])
            corner_box.pack(side="left", fill="both", expand=True, padx=5)
            self.post_fight_vars[corner] = self._build_post_fight_corner(corner_box)

        ttk.Button(frame, text="Save Result", command=self._on_save).pack(anchor="w", padx=5, pady=(10, 5))
        self.save_status_label = ttk.Label(frame, text="", foreground="gray", wraplength=800, justify="left")
        self.save_status_label.pack(anchor="w", padx=5, pady=(0, 5))

    def _build_post_fight_corner(self, parent) -> dict:
        vars_out = {}

        ttk.Label(parent, text="New Record (W-KO-L-D):").grid(row=0, column=0, columnspan=4,
                                                               sticky="w", padx=5, pady=(5, 2))
        record_row = ttk.Frame(parent)
        record_row.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 6))
        record_vars = {}
        for label, key in (("W", "wins"), ("KO", "knockouts"), ("L", "losses"), ("D", "draws")):
            ttk.Label(record_row, text=f"{label}:").pack(side="left", padx=(6, 2))
            var = tk.StringVar(value="0")
            ttk.Entry(record_row, textvariable=var, width=4).pack(side="left")
            record_vars[key] = var
        vars_out["new_record"] = record_vars

        for row, (label, key) in enumerate(
            (("Prize Money:", "prize_money"), ("Total Fans:", "total_fans"), ("XP Gained:", "xp_gained")),
            start=2,
        ):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            var = tk.StringVar(value="0")
            ttk.Entry(parent, textvariable=var, width=10).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            vars_out[key] = var

        ttk.Label(parent, text="Tendency Changes:", font=("TkDefaultFont", 9, "bold")).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 2))
        tendency_vars = {}
        for i, (key, label_a, label_b) in enumerate(TENDENCY_CHANGE_FIELDS):
            ttk.Label(parent, text=f"{label_a}/{label_b}:").grid(
                row=6 + i, column=0, sticky="w", padx=5, pady=1)
            var = tk.StringVar(value="0")
            ttk.Entry(parent, textvariable=var, width=6).grid(row=6 + i, column=1, sticky="w", padx=5, pady=1)
            tendency_vars[key] = var
        vars_out["tendency_changes"] = tendency_vars

        return vars_out

    # ---------- Lifecycle ----------
    def on_tab_shown(self):
        self.refresh_reference_data()

    def refresh_reference_data(self):
        self._gym_options = [(None, "FREE AGENT")] + [(g["id"], g["name"]) for g in self.api.get_gyms()]
        labels = [label for _gid, label in self._gym_options]
        self.red_gym_combo["values"] = labels
        self.blue_gym_combo["values"] = labels
        if not self.red_gym_var.get():
            self.red_gym_var.set("FREE AGENT")
        if not self.blue_gym_var.get():
            self.blue_gym_var.set("FREE AGENT")

        self._refresh_event_list()

    def _selected_gym_id(self, string_var: tk.StringVar):
        label = string_var.get()
        for gym_id, option_label in self._gym_options:
            if option_label == label:
                return gym_id
        return None

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
        events.sort(key=lambda e: e["event_id"])

        self._event_options = [
            (e["event_id"], f'{e["date"]} -- {e["headliner"]} (Event #{e["event_id"]})')
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

        all_fight_ids = (
            [event["main_event_fight_id"]] + event["co_main_fight_ids"] + event["undercard_fight_ids"]
        )
        meta_ready = [fid for fid in all_fight_ids if self.api.get_fight(fid)["status"] == STATUS_META]

        self._bout_options = [
            (fid, self._bout_label(fid)) for fid in meta_ready
        ]
        self.bout_combo["values"] = [label for _fid, label in self._bout_options]
        self.bout_var.set("")

    def _bout_label(self, fight_id: str) -> str:
        fight = self.api.get_fight(fight_id)
        red = self.api.get_fighter(fight["red_corner_fighter_id"])
        blue = self.api.get_fighter(fight["blue_corner_fighter_id"])
        #format_full_name(red["first_name"], red["last_name"], red["nickname"], red["placement"])
        red_name = f'{red["first_name"]} {red["last_name"]}'
        blue_name = f'{blue["first_name"]} {blue["last_name"]}'
        rounds = self.api.get_fight_rounds(fight_id)
        return f'{fight_id}: {red_name} vs {blue_name} ({fight["weight_limit"]} lbs, {rounds} rounds)'

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

        self.current_fight_id = fight_id
        self.current_fight = self.api.get_fight(fight_id)
        scheduled_rounds = self.api.get_fight_rounds(fight_id)

        self.stoppage_round_spin.config(to=scheduled_rounds)
        if int(self.stoppage_round_var.get()) > scheduled_rounds:
            self.stoppage_round_var.set(str(scheduled_rounds))

        red = self.api.get_fighter(self.current_fight["red_corner_fighter_id"])
        blue = self.api.get_fighter(self.current_fight["blue_corner_fighter_id"])
        red_name = format_full_name(red["first_name"], red["last_name"], red["nickname"], red["placement"])
        blue_name = format_full_name(blue["first_name"], blue["last_name"], blue["nickname"], blue["placement"])
        self.winner_combo["values"] = [f"Red -- {red_name}", f"Blue -- {blue_name}", DRAW_LABEL]
        self.winner_var.set("")

        self.build_status_label.config(
            text="Bout loaded. Set how the fight ended, then click \"Build Rounds & Scorecards\".")

    # ---------- Building the dynamic grids ----------
    def _build_rounds_and_scorecards(self):
        if self.current_fight is None:
            messagebox.showerror("No Bout Selected", "Select a bout first.")
            return

        sanctioned_rounds = self.api.get_fight_rounds(self._selected_fight_id())

        if self.end_type_var.get() == STOPPED:
            try:
                stoppage_round = int(self.stoppage_round_var.get())
            except ValueError:
                messagebox.showerror("Invalid Input", "Stoppage round must be a whole number.")
                return
            if not (1 <= stoppage_round <= sanctioned_rounds):
                messagebox.showerror("Invalid Input", f"Stoppage round must be between 1 and {sanctioned_rounds}.")
                return
            rounds_fought = stoppage_round
        else:
            rounds_fought = sanctioned_rounds

        self._build_scorecard_grid(sanctioned_rounds, rounds_fought if self.end_type_var.get() == STOPPED else None)
        self._build_punch_stat_grids(rounds_fought)

        self.build_status_label.config(
            text=f"Built {sanctioned_rounds}-round scorecards and {rounds_fought} round(s) of punch stats.")

    def _build_scorecard_grid(self, sanctioned_rounds: int, stoppage_round):
        for child in self.scorecards_scroll.inner.winfo_children():
            child.destroy()

        inner = self.scorecards_scroll.inner
        ttk.Label(inner, text="Judge / Fighter", width=16).grid(row=0, column=0, padx=2, pady=2)
        for r in range(1, sanctioned_rounds + 1):
            ttk.Label(inner, text=f"Rd {r}", width=6, anchor="center").grid(row=0, column=r, padx=2, pady=2)

        self.scorecard_vars = {}
        self.scorecard_entries = {}
        row = 1
        for judge in JUDGES:
            self.scorecard_vars[judge] = {}
            self.scorecard_entries[judge] = {}
            for corner in CORNERS:
                ttk.Label(inner, text=f"{judge.replace('_', ' ').title()} -- {CORNER_LABELS[corner]}",
                         width=22, anchor="w").grid(row=row, column=0, padx=2, pady=2, sticky="w")
                col_vars, col_entries = [], []
                for r in range(1, sanctioned_rounds + 1):
                    unscored = stoppage_round is not None and r >= stoppage_round
                    entry, var = _int_entry(inner, width=5, default="" if unscored else str(MAX_ROUND_SCORE))
                    entry.grid(row=row, column=r, padx=2, pady=2)
                    if unscored:
                        entry.configure(state="disabled")
                    col_vars.append(var)
                    col_entries.append(entry)
                self.scorecard_vars[judge][corner] = col_vars
                self.scorecard_entries[judge][corner] = col_entries
                row += 1

    def _build_punch_stat_grids(self, rounds_fought: int):
        self.punch_vars = {corner: {} for corner in CORNERS}
        self.knocked_down_vars = {corner: {} for corner in CORNERS}

        for corner in CORNERS:
            scroll = self.punch_scrolls[corner]
            for child in scroll.inner.winfo_children():
                child.destroy()
            inner = scroll.inner

            ttk.Label(inner, text="Field", width=14).grid(row=0, column=0, padx=2, pady=2)
            for r in range(1, rounds_fought + 1):
                ttk.Label(inner, text=f"Round {r}", width=13, anchor="center").grid(
                    row=0, column=r, padx=2, pady=2)

            for row_index, (field_key, field_label) in enumerate(PUNCH_STAT_ROWS, start=1):
                ttk.Label(inner, text=field_label, width=14, anchor="w").grid(
                    row=row_index, column=0, padx=2, pady=2, sticky="w")
                for r in range(1, rounds_fought + 1):
                    cell = ttk.Frame(inner)
                    cell.grid(row=row_index, column=r, padx=2, pady=2)
                    ttk.Label(cell, text="T:").pack(side="left")
                    t_entry, t_var = _int_entry(cell, width=4)
                    t_entry.pack(side="left")
                    ttk.Label(cell, text="L:").pack(side="left", padx=(4, 0))
                    l_entry, l_var = _int_entry(cell, width=4)
                    l_entry.pack(side="left")
                    self.punch_vars[corner].setdefault(r, {})[field_key] = {"thrown": t_var, "landed": l_var}

            kd_row = len(PUNCH_STAT_ROWS) + 1
            ttk.Label(inner, text="Knocked Down", width=14, anchor="w").grid(
                row=kd_row, column=0, padx=2, pady=2, sticky="w")
            for r in range(1, rounds_fought + 1):
                entry, var = _int_entry(inner, width=4)
                entry.grid(row=kd_row, column=r, padx=2, pady=2)
                self.knocked_down_vars[corner][r] = var

    # ---------- Gathering ----------

    def _gather_stoppage(self):
        if self.end_type_var.get() != STOPPED:
            return None
        return {
            "round": int(self.stoppage_round_var.get()),
            "losing_corner": "red_corner" if self.losing_corner_var.get() == "Red" else "blue_corner",
            "method": self.stoppage_method_var.get(),
            "time": f"{self.time_min_var.get()}'{self.time_sec_var.get()}\"{self.time_centisec_var.get()}",
        }

    def _gather_scorecards(self):
        scorecards = {}
        for judge in JUDGES:
            scorecards[judge] = {}
            for corner in CORNERS:
                scores = []
                for var in self.scorecard_vars[judge][corner]:
                    raw = var.get().strip()
                    scores.append(None if raw == "" else raw)
                scorecards[judge][corner] = scores
        return scorecards

    def _gather_rounds(self, rounds_fought: int):
        rounds = {corner: [] for corner in CORNERS}
        for corner in CORNERS:
            for r in range(1, rounds_fought + 1):
                round_vars = self.punch_vars[corner][r]
                punches = {
                    field: {"thrown": round_vars[field]["thrown"].get(), "landed": round_vars[field]["landed"].get()}
                    for field, _ in PUNCH_STAT_ROWS
                }
                rounds[corner].append({
                    "punches": punches,
                    "knocked_down": self.knocked_down_vars[corner][r].get(),
                })
        return rounds

    def _gather_outcome(self, red_id: int, blue_id: int):
        winner_label = self.winner_var.get()
        if winner_label == DRAW_LABEL:
            winner_id = None
        elif winner_label.startswith("Red"):
            winner_id = red_id
        elif winner_label.startswith("Blue"):
            winner_id = blue_id
        else:
            winner_id = None
        return {"winner_id": winner_id, "method": self.outcome_method_var.get()}

    def _gather_post_fight(self):
        post_fight = {}
        for corner in CORNERS:
            vars_dict = self.post_fight_vars[corner]
            post_fight[corner] = {
                "new_record": {k: v.get() for k, v in vars_dict["new_record"].items()},
                "prize_money": vars_dict["prize_money"].get(),
                "total_fans": vars_dict["total_fans"].get(),
                "xp_gained": vars_dict["xp_gained"].get(),
                "tendency_changes": {k: v.get() for k, v in vars_dict["tendency_changes"].items()},
            }
        return post_fight

    # ---------- Save ----------

    def _on_save(self):
        if self.current_fight_id is None:
            messagebox.showerror("No Bout Selected", "Select a bout first.")
            return
        if not self.punch_vars.get("red_corner") or not self.punch_vars.get("blue_corner"):
            messagebox.showerror("Not Built Yet", "Click \"Build Rounds & Scorecards\" before saving.")
            return

        stoppage = self._gather_stoppage()
        rounds_fought = stoppage["round"] if stoppage else self.current_fight["rounds"]

        red_id = self.current_fight["red_corner_fighter_id"]
        blue_id = self.current_fight["blue_corner_fighter_id"]

        result = {
            "gyms": {
                "red_corner": self._selected_gym_id(self.red_gym_var),
                "blue_corner": self._selected_gym_id(self.blue_gym_var),
            },
            "rounds": self._gather_rounds(rounds_fought),
            "scorecards": self._gather_scorecards(),
            "stoppage": stoppage,
            "outcome": self._gather_outcome(red_id, blue_id),
            "post_fight": self._gather_post_fight(),
        }

        try:
            self.api.save_fight_result(self.current_fight_id, result)
        except (FightError, GymError) as e:
            messagebox.showerror("Could Not Save Result", str(e))
            return

        messagebox.showinfo("Saved", f"Result saved for fight {self.current_fight_id}. Status is now Complete.")
        self.save_status_label.config(text=f"Saved fight {self.current_fight_id}.")
        self._on_event_selected()  # refresh the bout list -- this fight no longer shows (it's Complete now)
