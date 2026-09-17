import tkinter as tk
from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Rankings import RankingError, TYPE_DIVISION, TYPE_P4P

from ui.ranking_editor import RankingEditorFrame, MODE_RANKING
from ui.record_fans import RecordFansSection

P4P_LABEL = "Pound-for-Pound (P4P)"

class DivisionRankingsSection(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api
        self._division_options = []  # list of (weight_limit|None, label)

        self._build_controls()

        self.editor = RankingEditorFrame(self, api, mode=MODE_RANKING)
        self.editor.pack(fill="both", expand=True, padx=5, pady=5)

        ttk.Button(self, text="Save Rankings", command=self._on_save).pack(
            anchor="w", padx=10, pady=(0, 10))

        self.refresh_reference_data()

    def _build_controls(self):
        box = ttk.LabelFrame(self, text="Snapshot")
        box.pack(fill="x", padx=10, pady=10)

        ttk.Label(box, text="Month (YYYY-MM):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.month_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.month_var, width=12).grid(
            row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(box, text="Division:").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=5)
        self.division_var = tk.StringVar()
        self.division_combo = ttk.Combobox(box, textvariable=self.division_var,
                                           state="readonly", width=28)
        self.division_combo.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        self.division_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_division_changed())

        button_row = ttk.Frame(box)
        button_row.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))
        ttk.Button(button_row, text="Load Last Month", command=self._on_carry_forward).pack(
            side="left", padx=(0, 5))
        ttk.Button(button_row, text="Load This Month", command=self._on_load_month).pack(
            side="left", padx=5)

        self.status_label = ttk.Label(box, text="", foreground="gray",
                                      wraplength=600, justify="left")
        self.status_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

    # ---------- Reference data ----------
    def refresh_reference_data(self):
        """ Rebuild the division dropdown from weights.csv and re-filter who's eligible to be ranked """
        previous = self.division_var.get()

        self._division_options = [
            (wc["weight_limit"], f'{wc["weight_limit"]} - {wc["weight_class"]}')
            for wc in self.api.get_weight_classes()
        ]
        self._division_options.append((None, P4P_LABEL))

        self.division_combo["values"] = [label for _limit, label in self._division_options]

        if previous in self.division_combo["values"]:
            self.division_var.set(previous)
        elif self.division_combo["values"]:
            self.division_var.set(self.division_combo["values"][0])

        self._refresh_eligible_fighters()

    def _current_division(self):
        """Return (ranking_type, weight_limit) for the selected dropdown item."""
        label = self.division_var.get()
        for weight_limit, option_label in self._division_options:
            if option_label == label:
                if weight_limit is None:
                    return TYPE_P4P, None
                return TYPE_DIVISION, weight_limit
        return None, None

    def _refresh_eligible_fighters(self):
        """ P4P is open to everyone; a division is restricted to fighters registered at that weight class in fighters.csv """
        ranking_type, weight_limit = self._current_division()
        fighters = self.api.get_fighters()

        if ranking_type == TYPE_DIVISION:
            fighters = [f for f in fighters if f["weightclass"] == weight_limit]

        self.editor.set_eligible_fighters(fighters)

    def _on_division_changed(self):
        ranking_type, weight_limit = self._current_division()
        self._refresh_eligible_fighters()
        self.editor.clear()
        self._on_load_month()
        
        if ranking_type == "P4P":
            self.status_label.config(text=f"Division changed to P4P")
        else:
            self.status_label.config(text=f"Division changed to {weight_limit}lbs")

    # ---------- Loading ----------
    def _on_carry_forward(self):
        ranking_type, weight_limit = self._current_division()
        if ranking_type is None:
            messagebox.showerror("No Division", "Pick a division first.")
            return

        result = self.api.carry_forward_rankings(ranking_type, weight_limit)

        if result["source_month"] is None:
            self.editor.clear()
            self.status_label.config(
                text="No previous snapshot for this division -- starting from scratch.")
            return

        self.editor.load_entries(result["entries"])

        message = f'Loaded {result["source_month"]} as a starting point.'
        if result["dropped"]:
            parts = []
            for d in result["dropped"]:
                who = d.get("name") or f'FighterID {d["fighter_id"]}'
                parts.append(f'#{d["previous_rank"]} {who} ({d["reason"]})')
            message += " Dropped and everyone below moved up: " + "; ".join(parts) + "."
        self.status_label.config(text=message)

    def _on_load_month(self):
        ranking_type, weight_limit = self._current_division()
        if ranking_type is None:
            messagebox.showerror("No Division", "Pick a division first.")
            return

        month = self.month_var.get().strip()
        snapshot = self.api.get_ranking_snapshot(month, ranking_type, weight_limit)

        if not snapshot:
            self.status_label.config(text=f"No rankings saved for {month} in this division.")
            return

        self.editor.load_entries([
            {k: row[k] for k in ("fighter_id", "wins", "knockouts", "losses", "draws", "title")}
            for row in snapshot
        ])
        self.status_label.config(
            text=f"Loaded existing {weight_limit}lbs rankings for {month} (saving will overwrite).")

    # ---------- Saving ----------
    def _on_save(self):
        ranking_type, weight_limit = self._current_division()
        if ranking_type is None:
            messagebox.showerror("No Division", "Pick a division first.")
            return

        month = self.month_var.get().strip()

        if not self.editor.entries:
            messagebox.showerror("Nothing to Save", "Add at least one fighter first.")
            return

        try:
            self.api.save_ranking_snapshot(month, ranking_type, self.editor.entries, weight_limit)
        except RankingError as e:
            messagebox.showerror("Could Not Save Rankings", str(e))
            return

        messagebox.showinfo("Saved", f"Rankings saved for {month}.")
        self.status_label.config(
            text=f"Saved {len(self.editor.entries)} ranked fighters for {month}.")


class RankingsTab(ttk.Frame):
    """Top-level Rankings tab: divisions/P4P and fan favourites."""

    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)

        inner_notebook = ttk.Notebook(self)
        inner_notebook.pack(fill="both", expand=True)

        self.division_section = DivisionRankingsSection(inner_notebook, api)
        self.fans_section = RecordFansSection(inner_notebook, api)

        inner_notebook.add(self.division_section, text="Divisions / P4P")
        inner_notebook.add(self.fans_section, text="Fan Favourites")

    def on_tab_shown(self):
        self.division_section.refresh_reference_data()
        self.fans_section.refresh_reference_data()
