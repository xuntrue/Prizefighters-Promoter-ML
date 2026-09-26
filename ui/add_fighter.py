import tkinter as tk

from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import FighterError, INT_TO_STANCE, INT_TO_STYLE
from api.Records import RecordError

from ui.fighter_form import FighterFormFrame
from ui.fighter_preview import FighterPreviewFrame

class AddFighterTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        left = ttk.Frame(container)
        left.pack(side="left", fill="y", padx=10, pady=10)

        right = ttk.Frame(container)
        right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        ttk.Label(left, text="Add Fighter", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        self.form = FighterFormFrame(left, api)
        self.form.pack(anchor="w", pady=(10, 0))

        self._build_record_section(left)

        button_frame = ttk.Frame(left)
        button_frame.pack(anchor="w", pady=(10, 0))
        ttk.Button(button_frame, text="Save Fighter", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear", command=self._on_clear).pack(side="left", padx=5)

        self.preview = FighterPreviewFrame(right, api)
        self.preview.pack(fill="both", expand=True)

        # Live-update the preview whenever any form or record field changes
        self.form.bind_change(self._refresh_preview)
        self._refresh_preview()

    def _build_record_section(self, parent):
        record_frame = ttk.LabelFrame(parent, text="Record (leave at 0 for a debut fighter)")
        record_frame.pack(anchor="w", pady=(10, 0), fill="x")

        self.wins_var = tk.IntVar(value=0)
        self.knockouts_var = tk.IntVar(value=0)
        self.losses_var = tk.IntVar(value=0)
        self.draws_var = tk.IntVar(value=0)

        labels_and_vars = [
            ("Wins:", self.wins_var),
            ("Knockouts:", self.knockouts_var),
            ("Losses:", self.losses_var),
            ("Draws:", self.draws_var),
        ]
        for i, (label_text, var) in enumerate(labels_and_vars):
            ttk.Label(record_frame, text=label_text).grid(row=i, column=0, sticky="w", padx=5, pady=3)
            ttk.Spinbox(record_frame, from_=0, to=999, textvariable=var, width=6).grid(
                row=i, column=1, sticky="w", padx=5, pady=3
            )
            var.trace_add("write", lambda *_args: self._refresh_preview())

    # ---------- Tab lifecycle ----------
    def on_tab_shown(self):
        self.form.refresh_reference_data()
        self._refresh_preview()

    # ---------- Preview ----------
    def _read_record_fields_loosely(self) -> dict:
        result = {}
        for key, var in (
            ("wins", self.wins_var), ("knockouts", self.knockouts_var),
            ("losses", self.losses_var), ("draws", self.draws_var),
        ):
            try:
                result[key] = max(0, int(var.get()))
            except (tk.TclError, ValueError):
                result[key] = None
        return result

    def _gather_preview_data(self) -> dict:
        raw = self.form.get_raw_values()
        country = self.api.countries.get_by_code(raw["country"]) if raw["country"] else None

        weight_class_label = None
        if raw["weightclass"] is not None:
            match = next(
                (wc for wc in self.api.get_weight_classes() if wc["weight_limit"] == raw["weightclass"]),
                None,
            )
            if match:
                weight_class_label = f'{match["weight_limit"]} - {match["weight_class"]}'

        return {
            "first_name": raw["first_name"],
            "last_name": raw["last_name"],
            "nickname": raw["nickname"],
            "placement": raw["placement"],
            "hometown": raw["hometown"],
            "country_a2": raw["country"],
            "country_name": country["country_name"] if country else None,
            "birthdate": raw["birthdate"],
            "weight_class_label": weight_class_label,
            "reach": raw["reach"],
            "stance_label": INT_TO_STANCE.get(raw["stance"]),
            "style_label": INT_TO_STYLE.get(raw["style"]),
            **self._read_record_fields_loosely(),
        }

    def _refresh_preview(self):
        self.preview.render(self._gather_preview_data())

    # ---------- Save / clear ----------
    def _get_record_values(self):
        """Strict parse + validation for saving. Returns a dict on
        success, or None after showing an error message."""
        try:
            wins = int(self.wins_var.get())
            knockouts = int(self.knockouts_var.get())
            losses = int(self.losses_var.get())
            draws = int(self.draws_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Invalid Input", "Record values must be whole numbers.")
            return None

        if min(wins, knockouts, losses, draws) < 0:
            messagebox.showerror("Invalid Input", "Record values cannot be negative.")
            return None
        if knockouts > wins:
            messagebox.showerror("Invalid Input", "Knockouts cannot exceed total wins.")
            return None

        return {"wins": wins, "knockouts": knockouts, "losses": losses, "draws": draws}

    def _on_save(self):
        values = self.form.get_raw_values()

        if values["weightclass"] is None:
            messagebox.showerror("Invalid Input", "Please select a weight class.")
            return
        if values["reach"] is None:
            messagebox.showerror("Invalid Input", "Reach must be a whole number.")
            return
        if not values["country"]:
            messagebox.showerror("Invalid Input", "Please select a country.")
            return

        record_values = self._get_record_values()
        if record_values is None:
            return

        try:
            new_fighter = self.api.add_fighter(**values)
        except FighterError as e:
            messagebox.showerror("Could Not Save Fighter", str(e))
            return

        try:
            self.api.update_record(new_fighter["fighter_id"], **record_values)
        except RecordError as e:
            # Roll back the fighter so we don't leave one with no valid record.
            self.api.delete_fighter(new_fighter["fighter_id"])
            messagebox.showerror("Could Not Save Record", str(e))
            return

        messagebox.showinfo(
            "Fighter Added",
            f"{new_fighter['first_name']} {new_fighter['last_name']} "
            f"was added with FighterID {new_fighter['fighter_id']}.",
        )
        self._on_clear()

    def _on_clear(self):
        self.form.clear()
        self.wins_var.set(0)
        self.knockouts_var.set(0)
        self.losses_var.set(0)
        self.draws_var.set(0)
        self._refresh_preview()