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

        # Month selector
        ttk.Label(box, text="Month (YYYY-MM):").grid(row=0, column=2, sticky="w", padx=(15, 5), pady=5)
        self.month_var = tk.StringVar()
        self.month_combo = ttk.Combobox(box, textvariable=self.month_var, state="readonly", width=18)
        self.month_combo.grid(row=0, column=3, sticky="w", padx=5, pady=5)
        self.month_combo.bind("<<ComboboxSelected>>", self._on_month_changed)

        # Status label
        self.status_label = ttk.Label(box, text="", foreground="gray", wraplength=1000, justify="left")
        self.status_label.grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

    # ---------- Lifecycle ----------
    def refresh_reference_data(self):
        """Any fighter can be a fan favourite, so the dropdown is everyone."""
        self.editor.set_eligible_fighters(self.api.get_fighters())
        self.editor.refresh_table()

        self.editor.set_eligible_fighters(self.api.get_fighters())

        self._refresh_month_options()

        if self.month_var.get():
            self._on_month_changed()
        else:
            self.editor.clear()

    def _refresh_month_options(self):
        """ Refresh available snapshot months for the selected division """
        months = self.api.get_fan_months()
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
        months = self.api.get_fan_months()

        # Fetch month selected
        month = self.month_var.get().strip()
        if not month:
            self.editor.clear()
            return

        # Fetch 'current' snapshot
        if month not in months:
            snapshot = self.api.get_fan_snapshot(months[-1])
            self.status_label.config(text=f"No fan rankings saved for {month} ")
            i = len(months)
        else:
            snapshot = self.api.get_fan_snapshot(month)
            i = months.index(month)

        # Fetch previous month's snapshot
        if i > 0:
            prev_month = months[i-1]
            prev_snapshot = self.api.get_fan_snapshot(prev_month)
            self.editor.set_previous_ranks(prev_snapshot)

        if not snapshot:
            self.status_label.config(text=f"No fan rankings saved for {month} ")
            return

        self.editor.load_entries([
            {k: row[k] for k in ("fighter_id", "total_fans", "wins", "knockouts", "losses", "draws",
                                 "fighter_weight_limit")}
            for row in snapshot
        ])
        self.status_label.config(text=f"Loaded existing fan rankings for {month} (saving will overwrite).") 

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