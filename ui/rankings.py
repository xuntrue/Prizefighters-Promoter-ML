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

        # Division selector
        ttk.Label(box, text="Division:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.division_var = tk.StringVar()
        self.division_combo = ttk.Combobox(box, textvariable=self.division_var, state="readonly", width=28,)
        self.division_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.division_combo.bind("<<ComboboxSelected>>", self._on_division_changed)

        # Month selector
        ttk.Label(box, text="Month (YYYY-MM):").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=5)
        self.month_var = tk.StringVar()
        self.month_combo = ttk.Combobox(box, textvariable=self.month_var, state="readonly", width=18)
        self.month_combo.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        self.month_combo.bind("<<ComboboxSelected>>", self._on_month_changed)

        # Status label
        self.status_label = ttk.Label(box, text="", foreground="gray", wraplength=1000, justify="left")
        self.status_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

    # ---------- Reference data ----------
    def refresh_reference_data(self):
        """ Rebuild the division dropdown from weights.csv and re-filter who's eligible to be ranked """
        previous = self.division_var.get()

        self._division_options = [
            (wc["weight_limit"], f'{wc["weight_class"]}')
            for wc in self.api.get_weight_classes()
        ]
        self._division_options.append((None, P4P_LABEL))

        self.division_combo["values"] = [label for _limit, label in self._division_options]

        if previous in self.division_combo["values"]:
            self.division_var.set(previous)
        elif self.division_combo["values"]:
            self.division_var.set(self.division_combo["values"][-1])

        self._refresh_eligible_fighters()
        self._refresh_month_options()

        if self.month_var.get():
            self._on_month_changed()
        else:
            self.editor.clear()

    def _current_division(self):
        """ Return (ranking_type, weight_limit) for the selected dropdown item """
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

    def _on_division_changed(self, _event=None):
        self._refresh_eligible_fighters()
        self._refresh_month_options()
        self.editor.clear()   
        self.status_label.config(text="Select a month to view its rankings")

    def _refresh_month_options(self):
        """ Refresh available snapshot months for the selected division """
        ranking_type, weight_limit = self._current_division()
        if ranking_type is None:
            self.month_combo["values"] = []
            self.month_var.set("")
            return

        months = self.api.get_ranking_months(ranking_type, weight_limit)
        if len(months) < 1:
            months.append(f'1990-01') # Default starting value
            self.month_combo["values"] = months
            self.month_var.set(months[0])
            return

        if months[-1][5:] == '12':
            months.append(f'{int(months[-1][:4]) + 1}-01')
        else:
            months.append(f'{months[-1][:5]}{int(months[-1][5:]) + 1:02d}')

        self.month_combo["values"] = months
        if months:
            self.month_var.set(months[-2]) # Get 2nd last
        else:
            self.month_var.set("")
        self._on_month_changed()

    # ---------- Loading ----------
    def _on_month_changed(self, _event=None):
        ranking_type, weight_limit = self._current_division()
        if ranking_type is None:
            return

        months = self.api.get_ranking_months(ranking_type, weight_limit)
        if len(months) < 1:
            return

        # Fetch month selected
        month = self.month_var.get().strip()
        if not month:
            self.editor.clear()
            return

        # Fetch 'current' snapshot
        if month not in months:
            snapshot = self.api.get_ranking_snapshot(months[-1], ranking_type, weight_limit)
            self.status_label.config(text=f"No rankings saved for {month} in this division.")
            i = len(months)
        else:
            snapshot = self.api.get_ranking_snapshot(month, ranking_type, weight_limit)
            i = months.index(month)

        # Fetch previous month's snapshot
        if i > 0:
            prev_month = months[i-1]
            prev_snapshot = self.api.get_ranking_snapshot(prev_month, ranking_type, weight_limit)
            self.editor.set_previous_ranks(prev_snapshot)

        self.editor.load_entries([
            {
                k: row[k]
                for k in ("fighter_id", "wins", "knockouts", "losses", "draws", "title", "fighter_weight_limit")
            }
            for row in snapshot
        ])
        self.status_label.config(text=f"Loaded {weight_limit}lb rankings for {month}.")

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
    """ Top-level Rankings tab: divisions/P4P and fan favourites """
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