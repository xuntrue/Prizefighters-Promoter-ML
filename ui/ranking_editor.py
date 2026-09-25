"""
ranking_editor.py

Shared editor widget for building a ranking snapshot. Used by both
rankings.py (divisional + P4P, which have a Title checkbox) and
record_fans.py (fan favourites, which have a Total Fans count instead).

The two modes differ only in one column, so the widget is parameterised
with `mode` rather than duplicated. It holds the working snapshot in a
plain Python list (self.entries) -- index 0 is rank #1 -- and re-renders
the table from that list. Nothing is written to disk until the owning
screen calls the API on Save.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import format_full_name

MODE_RANKING = "ranking"   # divisional / P4P: has a Title flag
MODE_FANS = "fans"         # fan favourites: has a Total Fans count


class RankingEditorFrame(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI, mode: str = MODE_RANKING, max_entries=None):
        super().__init__(parent)
        self.api = api
        self.mode = mode
        self.max_entries = max_entries

        self.entries = []            # working snapshot; index 0 == rank #1
        self._fighter_options = []   # list of (fighter_id, display label)
        self.previous_ranks = None   # {fighter_id: rank} from the most recent existing prior month

        self._build_table()
        self._build_entry_controls()

    # ---------- Construction ----------

    def _build_table(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        if self.mode == MODE_RANKING:
            # "division" shows each fighter's own registered weight class --
            # redundant for a DIVISION snapshot (it's always the selected
            # division) but the whole point for P4P, where fighters span
            # every division: seeing it while building the list is what
            # lets which-divisions-are-strongest analysis start at
            # data-entry time, not just after the fact.
            columns = ("rank", "delta", "fighter", "division", "record", "title")
            headings = ("#", "Chg", "Fighter", "Division", "Record", "Title")
            widths = (40, 55, 175, 150, 110, 60)
        else:
            # Fan favourites aren't restricted to one division either, so
            # the same "which divisions draw the most interest" analysis
            # applies here.
            columns = ("rank", "delta", "fighter", "division", "record", "fans")
            headings = ("#", "Chg", "Fighter", "Division", "Record", "Total Fans")
            widths = (40, 55, 175, 150, 110, 100)

        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col, heading, width in zip(columns, headings, widths):
            self.tree.heading(col, text=heading)
            anchor = "w" if col == "fighter" else "center"
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="left", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        side = ttk.Frame(frame)
        side.pack(side="left", fill="y", padx=8)
        ttk.Button(side, text="Move Up", command=lambda: self._move(-1)).pack(fill="x", pady=2)
        ttk.Button(side, text="Move Down", command=lambda: self._move(1)).pack(fill="x", pady=2)
        ttk.Button(side, text="Remove", command=self._remove_selected).pack(fill="x", pady=(12, 2))
        ttk.Button(side, text="Clear All", command=self.clear).pack(fill="x", pady=2)

    def _build_entry_controls(self):
        box = ttk.LabelFrame(self, text="Add / Update Entry")
        box.pack(fill="x", padx=5, pady=(0, 5))

        ttk.Label(box, text="Fighter:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.fighter_var = tk.StringVar()
        self.fighter_combo = ttk.Combobox(box, textvariable=self.fighter_var, state="readonly", width=34)
        self.fighter_combo.grid(row=0, column=1, columnspan=3, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="W:").grid(row=1, column=0, sticky="e", padx=(5, 0), pady=4)
        self.wins_var = tk.IntVar(value=0)
        ttk.Spinbox(box, from_=0, to=999, textvariable=self.wins_var, width=5).grid(
            row=1, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="KO:").grid(row=1, column=2, sticky="e", padx=(5, 0), pady=4)
        self.knockouts_var = tk.IntVar(value=0)
        ttk.Spinbox(box, from_=0, to=999, textvariable=self.knockouts_var, width=5).grid(
            row=1, column=3, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="L:").grid(row=2, column=0, sticky="e", padx=(5, 0), pady=4)
        self.losses_var = tk.IntVar(value=0)
        ttk.Spinbox(box, from_=0, to=999, textvariable=self.losses_var, width=5).grid(
            row=2, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="D:").grid(row=2, column=2, sticky="e", padx=(5, 0), pady=4)
        self.draws_var = tk.IntVar(value=0)
        ttk.Spinbox(box, from_=0, to=999, textvariable=self.draws_var, width=5).grid(
            row=2, column=3, sticky="w", padx=5, pady=4)

        if self.mode == MODE_RANKING:
            self.title_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(box, text="Holds a title in this division", variable=self.title_var).grid(
                row=3, column=0, columnspan=4, sticky="w", padx=5, pady=4)
        else:
            ttk.Label(box, text="Total Fans:").grid(row=3, column=0, sticky="e", padx=(5, 0), pady=4)
            self.total_fans_var = tk.IntVar(value=0)
            ttk.Spinbox(box, from_=0, to=100_000_000, textvariable=self.total_fans_var, width=12).grid(
                row=3, column=1, columnspan=3, sticky="w", padx=5, pady=4)

        button_row = ttk.Frame(box)
        button_row.grid(row=4, column=0, columnspan=4, sticky="w", padx=5, pady=(8, 5))
        ttk.Button(button_row, text="Add to Bottom", command=self._add_entry).pack(side="left", padx=(0, 5))
        ttk.Button(button_row, text="Update Selected", command=self._update_selected).pack(side="left", padx=5)
        ttk.Button(button_row, text="Fill Record From File",
                   command=self._fill_record_from_file).pack(side="left", padx=5)

    # ---------- Eligible fighters ----------
    def set_eligible_fighters(self, fighters: list):
        """Restrict the fighter dropdown to a given list of fighter dicts.
        Divisional rankings pass only fighters registered to that weight
        class; P4P and fan rankings pass everyone."""
        self._fighter_options = [
            (
                f["fighter_id"],
                f'#{f["fighter_id"]} {format_full_name(f["first_name"], f["last_name"], f["nickname"], f["placement"])}',
            )
            for f in fighters
        ]
        self.fighter_combo["values"] = [label for _fid, label in self._fighter_options]
        self.fighter_var.set("")

    def _selected_fighter_id(self):
        label = self.fighter_var.get()
        for fighter_id, option_label in self._fighter_options:
            if option_label == label:
                return fighter_id
        return None

    def _label_for_fighter(self, fighter_id: int) -> str:
        for fid, label in self._fighter_options:
            if fid == fighter_id:
                return label
        fighter = self.api.get_fighter(fighter_id)
        if fighter is None:
            return f"#{fighter_id} (unknown fighter)"
        return (f'#{fighter_id} '
                f'{format_full_name(fighter["first_name"], fighter["last_name"], fighter["nickname"], fighter["placement"])}')

    def _division_label_for_entry(self, entry: dict) -> str:
        """Division label for one row. Prefers the entry's OWN stored
        fighter_weight_limit -- the fighter's actual division AT THE TIME
        of a historical snapshot, read straight from rankings.csv -- over
        a live lookup, since a fighter's current registration can have
        changed since that snapshot was recorded. Falls back to a live
        lookup only for an entry that has no fighter_weight_limit at all
        yet (freshly added, or carried forward into a month that hasn't
        been saved yet), where a live value is the best guess available."""
        weight_limit = entry.get("fighter_weight_limit")

        if weight_limit is None:
            fighter = self.api.get_fighter(entry["fighter_id"])
            if fighter is None:
                return "?"
            weight_limit = fighter["weightclass"]

        for wc in self.api.get_weight_classes():
            if wc["weight_limit"] == weight_limit:
                return f'{wc["weight_class"]}'
        return str(weight_limit)

    # ---------- Rank-change column ----------

    def set_previous_ranks(self, previous_ranks):
        """Set the {fighter_id: rank} lookup from the most recent existing
        PRIOR month, used to render the "Chg" column. Pass None when no
        prior snapshot exists at all for this division/type (e.g. the
        very first month ever recorded) -- in that case the column stays
        blank for every row, rather than treating everyone as new (NR).
        Call this, then load_entries()/refresh_table(), whenever the
        displayed month or division changes."""
        self.previous_ranks = previous_ranks

    def _delta_label(self, fighter_id: int, current_rank: int) -> str:
        """
        '\u25b2{delta}' -- moved up (a better, lower rank number) since
                            the last existing snapshot
        '\u25bc{delta}' -- dropped since the last existing snapshot
        'NR'            -- wasn't ranked at all last time (new entrant)
        ''              -- either no prior snapshot exists to compare
                            against, or the rank is unchanged

        Deliberately says nothing about a fighter who WAS ranked last
        month but is absent this month -- that's not this column's job,
        and there's no row to attach the label to anyway since this is
        only ever called for a fighter present in the CURRENT list.
        """
        print(f"For #{fighter_id}, self.previous_ranks = {self.previous_ranks}")
        if self.previous_ranks is None:
            return ""

        previous_rank = self.previous_ranks.get(fighter_id)
        if previous_rank is None:
            return "NR"
        if previous_rank == current_rank:
            return ""

        delta = abs(previous_rank - current_rank)
        return f"\u25b2{delta}" if current_rank < previous_rank else f"\u25bc{delta}"

    # ---------- Table rendering ----------
    def refresh_table(self):
        selected_index = self._selected_index()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, entry in enumerate(self.entries):
            rank = index + 1
            record = f'{entry["wins"]}({entry["knockouts"]})-{entry["losses"]}-{entry["draws"]}'
            fighter_label = self._label_for_fighter(entry["fighter_id"])
            division_label = self._division_label_for_entry(entry)
            delta_label = self._delta_label(entry["fighter_id"], rank)
            #print(f"Entry: {entry['fighter_id']}, Rank: {rank}, Delta: {delta_label}")

            if self.mode == MODE_RANKING:
                last_col = "\u2605" if entry.get("title") else ""
            else:
                last_col = f'{entry.get("total_fans", 0):,}'
            values = (index + 1, fighter_label, division_label, record, last_col)
            values = (rank, delta_label, fighter_label, division_label, record, last_col)

            self.tree.insert("", "end", iid=str(index), values=values)

        if selected_index is not None and 0 <= selected_index < len(self.entries):
            self.tree.selection_set(str(selected_index))

    def _selected_index(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _on_row_selected(self, event):
        index = self._selected_index()
        if index is None:
            return
        entry = self.entries[index]
        self.fighter_var.set(self._label_for_fighter(entry["fighter_id"]))
        self.wins_var.set(entry["wins"])
        self.knockouts_var.set(entry["knockouts"])
        self.losses_var.set(entry["losses"])
        self.draws_var.set(entry["draws"])
        if self.mode == MODE_RANKING:
            self.title_var.set(bool(entry.get("title")))
        else:
            self.total_fans_var.set(entry.get("total_fans", 0))

    # ---------- Editing ----------

    def _read_form(self):
        """Read the entry controls into a dict, or None after showing an error."""
        fighter_id = self._selected_fighter_id()
        if fighter_id is None:
            messagebox.showerror("No Fighter", "Pick a fighter from the dropdown first.")
            return None

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

        entry = {"fighter_id": fighter_id, "wins": wins, "knockouts": knockouts,
                 "losses": losses, "draws": draws}

        if self.mode == MODE_RANKING:
            entry["title"] = 1 if self.title_var.get() else 0
        else:
            try:
                total_fans = int(self.total_fans_var.get())
            except (tk.TclError, ValueError):
                messagebox.showerror("Invalid Input", "Total Fans must be a whole number.")
                return None
            if total_fans < 0:
                messagebox.showerror("Invalid Input", "Total Fans cannot be negative.")
                return None
            entry["total_fans"] = total_fans

        return entry

    def _add_entry(self):
        entry = self._read_form()
        if entry is None:
            return

        if self.max_entries is not None and len(self.entries) >= self.max_entries:
            messagebox.showerror(
                "Limit Reached", f"This ranking holds at most {self.max_entries} fighters.")
            return

        if any(e["fighter_id"] == entry["fighter_id"] for e in self.entries):
            messagebox.showerror("Already Ranked", "That fighter is already in this ranking.")
            return

        self.entries.append(entry)
        self.refresh_table()

    def _update_selected(self):
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("No Selection", "Select a ranked fighter to update.")
            return

        entry = self._read_form()
        if entry is None:
            return

        duplicate = any(
            e["fighter_id"] == entry["fighter_id"] for i, e in enumerate(self.entries) if i != index
        )
        if duplicate:
            messagebox.showerror("Already Ranked", "That fighter is already in this ranking.")
            return

        self.entries[index] = entry
        self.refresh_table()

    def _fill_record_from_file(self):
        """Pull the fighter's current record out of records.csv into the
        record spinboxes, so the user doesn't retype what we already know."""
        fighter_id = self._selected_fighter_id()
        if fighter_id is None:
            messagebox.showerror("No Fighter", "Pick a fighter from the dropdown first.")
            return

        record = self.api.get_record(fighter_id)
        if record is None:
            messagebox.showinfo("No Record", "That fighter has no record on file yet.")
            return

        self.wins_var.set(record["wins"])
        self.knockouts_var.set(record["knockouts"])
        self.losses_var.set(record["losses"])
        self.draws_var.set(record["draws"])

    def _move(self, offset: int):
        index = self._selected_index()
        if index is None:
            return
        target = index + offset
        if not (0 <= target < len(self.entries)):
            return
        self.entries[index], self.entries[target] = self.entries[target], self.entries[index]
        self.refresh_table()
        self.tree.selection_set(str(target))

    def _remove_selected(self):
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("No Selection", "Select a ranked fighter to remove.")
            return
        self.entries.pop(index)
        self.refresh_table()

    def clear(self):
        self.entries = []
        self.refresh_table()

    # ---------- Bulk load ----------

    def load_entries(self, entries: list):
        """Replace the working snapshot wholesale (used by carry-forward
        and when viewing an existing month)."""
        self.entries = [dict(e) for e in entries]
        self.refresh_table()
