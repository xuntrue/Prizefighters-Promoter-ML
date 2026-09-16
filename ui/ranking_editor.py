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

        self._build_table()
        self._build_entry_controls()

    # ---------- Construction ----------
    def _build_table(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        if self.mode == MODE_RANKING:
            columns = ("rank", "fighter", "record", "title")
            headings = ("#", "Fighter", "Record", "Title")
            widths = (40, 220, 120, 60)
        else:
            columns = ("rank", "fighter", "record", "fans")
            headings = ("#", "Fighter", "Record", "Total Fans")
            widths = (40, 220, 120, 100)

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
        self.fighter_combo = ttk.Combobox(box, textvariable=self.fighter_var,
                                            state="readonly", width=34)
        self.fighter_combo.grid(row=0, column=1, sticky="w", padx=5, pady=4)

        record_row = ttk.Frame(box)
        record_row.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=4)

        self.wins_var = tk.IntVar(value=0)
        self.knockouts_var = tk.IntVar(value=0)
        self.losses_var = tk.IntVar(value=0)
        self.draws_var = tk.IntVar(value=0)

        for label, var in (("W:", self.wins_var), ("KO:", self.knockouts_var),
                            ("L:", self.losses_var), ("D:", self.draws_var)):
            ttk.Label(record_row, text=label).pack(side="left", padx=(10, 2))
            ttk.Spinbox(record_row, from_=0, to=999, textvariable=var,
                        width=5).pack(side="left")

        if self.mode == MODE_RANKING:
            self.title_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(box, text="Holds a title in this division",
                            variable=self.title_var).grid(
                row=2, column=0, columnspan=2, sticky="w", padx=5, pady=4)
        else:
            fans_row = ttk.Frame(box)
            fans_row.grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=4)
            ttk.Label(fans_row, text="Total Fans:").pack(side="left", padx=(0, 5))
            self.total_fans_var = tk.IntVar(value=0)
            ttk.Spinbox(fans_row, from_=0, to=100_000_000,
                        textvariable=self.total_fans_var, width=12).pack(side="left")

        button_row = ttk.Frame(box)
        button_row.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=(8, 5))
        ttk.Button(button_row, text="Add to Bottom", command=self._add_entry).pack(side="left", padx=(0, 5))
        ttk.Button(button_row, text="Update Selected", command=self._update_selected).pack(side="left", padx=5)
        ttk.Button(button_row, text="Fill Record From File", command=self._fill_record_from_file).pack(side="left", padx=5)

    # ---------- Eligible fighters ----------
    def set_eligible_fighters(self, fighters: list):
        """ Restrict the fighter dropdown to a given list of fighter dicts """
        self._fighter_options = sorted(
            (
                (
                    f["fighter_id"],
                    format_full_name(f["first_name"], f["last_name"], f["nickname"], f["placement"]),
                )
                for f in fighters
            ),
            key=lambda option: option[1].lower(),
        )
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
            return f"(unknown fighter)"
        return (f'{format_full_name(fighter["first_name"], fighter["last_name"], fighter["nickname"], fighter["placement"])}')

    # ---------- Table rendering ----------
    def refresh_table(self):
        selected_index = self._selected_index()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, entry in enumerate(self.entries):
            record = f'{entry["wins"]}-{entry["losses"]}-{entry["draws"]} ({entry["knockouts"]} KO)'
            if self.mode == MODE_RANKING:
                last_col = "★" if entry.get("title") else ""
            else:
                last_col = f'{entry.get("total_fans", 0):,}'
            self.tree.insert(
                "", "end", iid=str(index),
                values=(index + 1, self._label_for_fighter(entry["fighter_id"]), record, last_col),
            )

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
