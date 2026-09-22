import tkinter as tk

from tkinter import ttk, messagebox
from datetime import date, datetime

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import format_full_name
from api.Fights import FightError, VALID_ROUNDS, VALID_ROUND_MINUTES, DATE_FORMAT, STATUS_SCHEDULED

STATUS_FILTER_UPCOMING = "Upcoming (from reference date)"
STATUS_FILTER_ALL = "All Fights"

def _fighter_label(fighter: dict) -> str:
    return f'{fighter["first_name"]} {fighter["last_name"]}'

class ScheduleFightTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api
        self._fighter_options = []  # list of (fighter_id, label), filtered to the chosen division

        self._build_reference_date()
        self._build_form()
        self._build_table()

        self.refresh_reference_data()

    # ---------- Construction ----------
    def _build_reference_date(self):
        date_frame = ttk.LabelFrame(self, text="Game's Current Date (defines \"upcoming\")")
        date_frame.pack(fill="x", padx=10, pady=(10, 5))

        today = date.today()
        self.ref_day_var = tk.StringVar(value=str(today.day))
        self.ref_month_var = tk.StringVar(value=str(today.month))
        self.ref_year_var = tk.StringVar(value=str(today.year))

        ttk.Label(date_frame, text="Day:").pack(side="left", padx=(5, 2))
        ttk.Spinbox(date_frame, from_=1, to=31, textvariable=self.ref_day_var, width=4,
                    command=self._refresh_table).pack(side="left")
        ttk.Label(date_frame, text="Month:").pack(side="left", padx=(10, 2))
        ttk.Spinbox(date_frame, from_=1, to=12, textvariable=self.ref_month_var, width=4,
                    command=self._refresh_table).pack(side="left")
        ttk.Label(date_frame, text="Year:").pack(side="left", padx=(10, 2))
        ttk.Spinbox(date_frame, from_=1900, to=2100, textvariable=self.ref_year_var, width=6,
                    command=self._refresh_table).pack(side="left")

        for var in (self.ref_day_var, self.ref_month_var, self.ref_year_var):
            var.trace_add("write", lambda *args: self._refresh_table())

    def _build_form(self):
        form = ttk.LabelFrame(self, text="Schedule a Fight")
        form.pack(fill="x", padx=10, pady=5)

        ttk.Label(form, text="Date (dd-mm-yyyy):").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.date_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.date_var, width=14).grid(
            row=0, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(form, text="Weight Class:").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=4)
        self.weight_class_var = tk.StringVar()
        self.weight_class_combo = ttk.Combobox(form, textvariable=self.weight_class_var,
                                               state="readonly", width=24)
        self.weight_class_combo.grid(row=0, column=3, sticky="w", padx=5, pady=4)
        self.weight_class_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_weight_class_changed())

        ttk.Label(form, text="Red Corner:").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        self.red_var = tk.StringVar()
        self.red_combo = ttk.Combobox(form, textvariable=self.red_var, state="readonly", width=30)
        self.red_combo.grid(row=1, column=1, columnspan=2, sticky="w", padx=5, pady=4)

        ttk.Label(form, text="Blue Corner:").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        self.blue_var = tk.StringVar()
        self.blue_combo = ttk.Combobox(form, textvariable=self.blue_var, state="readonly", width=30)
        self.blue_combo.grid(row=2, column=1, columnspan=2, sticky="w", padx=5, pady=4)

        ttk.Label(form, text="Rounds:").grid(row=3, column=0, sticky="w", padx=5, pady=4)
        self.rounds_var = tk.StringVar(value=str(VALID_ROUNDS[0]))
        ttk.Combobox(form, textvariable=self.rounds_var, values=[str(r) for r in VALID_ROUNDS],
                    state="readonly", width=6).grid(row=3, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(form, text="Round Length (min):").grid(row=3, column=2, sticky="w", padx=(15, 5), pady=4)
        self.round_minutes_var = tk.StringVar(value=str(VALID_ROUND_MINUTES[0]))
        ttk.Combobox(form, textvariable=self.round_minutes_var,
                    values=[str(m) for m in VALID_ROUND_MINUTES],
                    state="readonly", width=6).grid(row=3, column=3, sticky="w", padx=5, pady=4)

        self.championship_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Championship bout (a title is on the line)",
                        variable=self.championship_var).grid(
            row=4, column=0, columnspan=4, sticky="w", padx=5, pady=(4, 8))

        ttk.Button(form, text="Schedule Fight", command=self._on_schedule).grid(
            row=5, column=0, sticky="w", padx=5, pady=(0, 8))

    def _build_table(self):
        table_frame = ttk.LabelFrame(self, text="Fights")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        top_bar = ttk.Frame(table_frame)
        top_bar.pack(fill="x", padx=5, pady=5)

        ttk.Label(top_bar, text="Show:").pack(side="left")
        self.filter_var = tk.StringVar(value=STATUS_FILTER_UPCOMING)
        filter_combo = ttk.Combobox(
            top_bar, textvariable=self.filter_var, state="readonly", width=28,
            values=[STATUS_FILTER_UPCOMING, STATUS_FILTER_ALL],
        )
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_table())

        ttk.Button(top_bar, text="Cancel Selected Fight", command=self._on_cancel).pack(
            side="left", padx=15)

        columns = ("fight_id", "date", "weight_class", "red", "blue", "championship", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        headings = {
            "fight_id": "FightID", "date": "Date", "weight_class": "Division",
            "red": "Red Corner", "blue": "Blue Corner", "championship": "Title Bout", "status": "Status",
        }
        widths = {"fight_id": 80, "date": 90, "weight_class": 130, "red": 150,
                 "blue": 150, "championship": 80, "status": 90}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center" if col != "red" and col != "blue" else "w")
        self.tree.pack(fill="both", expand=True, padx=5, pady=(0, 5))

    # ---------- Reference data ----------
    def on_tab_shown(self):
        self.refresh_reference_data()

    def refresh_reference_data(self):
        self.weight_class_combo["values"] = [
            f'{wc["weight_limit"]} - {wc["weight_class"]}' for wc in self.api.get_weight_classes()
        ]
        self._on_weight_class_changed()
        self._refresh_table()

    def _current_weight_limit(self):
        label = self.weight_class_var.get()
        if not label:
            return None
        try:
            return int(label.split(" - ")[0].strip())
        except ValueError:
            return None

    def _on_weight_class_changed(self):
        weight_limit = self._current_weight_limit()
        fighters = self.api.get_fighters()
        if weight_limit is not None:
            fighters = [f for f in fighters if f["weightclass"] == weight_limit]
        fighters = sorted(fighters, key=lambda f: (f["first_name"].lower(), f["last_name"].lower()))

        self._fighter_options = [(f["fighter_id"], _fighter_label(f)) for f in fighters]
        labels = [label for _fid, label in self._fighter_options]
        self.red_combo["values"] = labels
        self.blue_combo["values"] = labels
        self.red_var.set("")
        self.blue_var.set("")

    def _selected_fighter_id(self, string_var: tk.StringVar):
        label = string_var.get()
        for fighter_id, option_label in self._fighter_options:
            if option_label == label:
                return fighter_id
        return None

    # ---------- Table ----------
    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        fights = self.api.get_fights()

        if self.filter_var.get() == STATUS_FILTER_UPCOMING:
            try:
                ref_date = date(int(self.ref_year_var.get()), int(self.ref_month_var.get()),
                                int(self.ref_day_var.get()))
            except (ValueError, tk.TclError):
                ref_date = date.today()

            def is_upcoming(fight):
                try:
                    fight_date = datetime.strptime(fight["date"], DATE_FORMAT).date()
                except ValueError:
                    return False
                return fight_date >= ref_date

            fights = [f for f in fights if is_upcoming(f)]

        for fight in fights:
            red = self.api.get_fighter(fight["red_corner_fighter_id"])
            blue = self.api.get_fighter(fight["blue_corner_fighter_id"])
            self.tree.insert(
                "", "end", iid=fight["fight_id"],
                values=(
                    fight["fight_id"],
                    fight["date"],
                    fight["weight_limit"],
                    _fighter_label(red) if red else f'FighterID {fight["red_corner_fighter_id"]}',
                    _fighter_label(blue) if blue else f'FighterID {fight["blue_corner_fighter_id"]}',
                    "Yes" if fight["championship"] else "",
                    fight["status"],
                ),
            )

    # ---------- Actions ----------
    def _on_schedule(self):
        red_id = self._selected_fighter_id(self.red_var)
        blue_id = self._selected_fighter_id(self.blue_var)
        weight_limit = self._current_weight_limit()

        if weight_limit is None:
            messagebox.showerror("Invalid Input", "Please select a weight class.")
            return
        if red_id is None or blue_id is None:
            messagebox.showerror("Invalid Input", "Please select both a red corner and a blue corner fighter.")
            return

        try:
            rounds = int(self.rounds_var.get())
            round_minutes = int(self.round_minutes_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Rounds and round length must be selected.")
            return

        try:
            new_fight = self.api.schedule_fight(
                date=self.date_var.get().strip(),
                weight_limit=weight_limit,
                red_corner_fighter_id=red_id,
                blue_corner_fighter_id=blue_id,
                rounds=rounds,
                round_minutes=round_minutes,
                championship=self.championship_var.get(),
            )
        except FightError as e:
            messagebox.showerror("Could Not Schedule Fight", str(e))
            return

        messagebox.showinfo("Fight Scheduled", f'Fight {new_fight["fight_id"]} scheduled.')
        self.date_var.set("")
        self.red_var.set("")
        self.blue_var.set("")
        self.championship_var.set(False)
        self._refresh_table()

    def _on_cancel(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select a fight to cancel.")
            return

        fight_id = selection[0]
        fight = self.api.get_fight(fight_id)
        if fight is None:
            return

        if fight["status"] != STATUS_SCHEDULED:
            messagebox.showerror(
                "Cannot Cancel",
                f'Fight {fight_id} is {fight["status"]}, not Scheduled -- only scheduled fights can be cancelled.',
            )
            return

        if not messagebox.askyesno("Confirm Cancel", f"Cancel fight {fight_id}?"):
            return

        try:
            self.api.cancel_fight(fight_id)
        except FightError as e:
            messagebox.showerror("Error", str(e))
            return

        self._refresh_table()
