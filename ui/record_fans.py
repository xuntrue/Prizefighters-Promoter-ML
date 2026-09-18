import tkinter as tk

from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Rankings import RankingError, MAX_FAN_RANKS
from ui.ranking_editor import RankingEditorFrame, MODE_FANS


class RecordFansSection(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api

        self._build_controls()

        self.editor = RankingEditorFrame(self, api, mode=MODE_FANS, max_entries=MAX_FAN_RANKS)
        self.editor.pack(fill="both", expand=True, padx=5, pady=5)

        ttk.Button(self, text="Save Fan Rankings", command=self._on_save).pack(
            anchor="w", padx=10, pady=(0, 10))

        self.refresh_reference_data()

    def _build_controls(self):
        box = ttk.LabelFrame(self, text="Snapshot")
        box.pack(fill="x", padx=10, pady=10)

        ttk.Label(box, text="Month (YYYY-MM):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.month_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.month_var, width=12).grid(
            row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Button(box, text="Load Last Month", command=self._on_carry_forward).grid(
            row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Button(box, text="Load This Month", command=self._on_load_month).grid(
            row=0, column=3, sticky="w", padx=5, pady=5)
        ttk.Button(box, text="Load Next Month", command=self._on_load_next_month).grid(
            row=0, column=4, sticky="w", padx=5, pady=5)

        self.status_label = ttk.Label(box, text="", foreground="gray", wraplength=600, justify="left")
        self.status_label.grid(row=1, column=0, columnspan=5, sticky="w", padx=5, pady=(0, 5))

    # ---------- Lifecycle ----------
    def refresh_reference_data(self):
        """Any fighter can be a fan favourite, so the dropdown is everyone."""
        self.editor.set_eligible_fighters(self.api.get_fighters())
        self.editor.refresh_table()

    # ---------- Loading ----------
    def _on_carry_forward(self):
        result = self.api.carry_forward_fan_rankings()

        if result["source_month"] is None:
            self.editor.clear()
            self.status_label.config(text="No previous fan rankings on file -- starting from scratch.")
            return

        self.editor.load_entries(result["entries"])

        message = f'Loaded {result["source_month"]} as a starting point.'
        if result["dropped"]:
            dropped_text = "; ".join(
                f'#{d["previous_rank"]} FighterID {d["fighter_id"]} ({d["reason"]})'
                for d in result["dropped"]
            )
            message += f' Dropped: {dropped_text}.'
        self.status_label.config(text=message)

    def _on_load_month(self):
        month = self.month_var.get().strip()
        snapshot = self.api.get_fan_snapshot(month)

        if not snapshot:
            self.status_label.config(text=f"No fan rankings saved for {month}.")
            return

        self.editor.load_entries([
            {k: row[k] for k in ("fighter_id", "total_fans", "wins", "knockouts", "losses", "draws")}
            for row in snapshot
        ])
        self.status_label.config(text=f"Loaded existing fan rankings for {month} (saving will overwrite).")

    def _on_load_next_month(self):
        """One-click "figure out next month, then load last month's roster"."""
        next_month = self.api.get_next_fan_month()
        if next_month is None:
            messagebox.showinfo(
                "No Existing Rankings",
                "There's no previous fan rankings snapshot to advance from -- "
                "enter a starting month manually.",
            )
            return

        result = self.api.carry_forward_fan_rankings()
        self.month_var.set(next_month)
        self.editor.load_entries(result["entries"])

        message = f'Advanced to {next_month}, starting from {result["source_month"]}\'s roster.'
        if result["dropped"]:
            parts = [
                f'#{d["previous_rank"]} FighterID {d["fighter_id"]} ({d["reason"]})'
                for d in result["dropped"]
            ]
            message += " Dropped: " + "; ".join(parts) + "."
        self.status_label.config(text=message)

    # ---------- Saving ----------
    def _on_save(self):
        month = self.month_var.get().strip()

        if not self.editor.entries:
            messagebox.showerror("Nothing to Save", "Add at least one fighter first.")
            return

        try:
            self.api.save_fan_snapshot(month, self.editor.entries)
        except RankingError as e:
            messagebox.showerror("Could Not Save Fan Rankings", str(e))
            return

        messagebox.showinfo("Saved", f"Fan rankings saved for {month}.")
        self.status_label.config(text=f"Saved {len(self.editor.entries)} fan favourites for {month}.")
