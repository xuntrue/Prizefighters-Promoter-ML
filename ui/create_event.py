import tkinter as tk

from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import format_full_name
from api.Events import EventError

ROLE_MAIN = "Main Event"
ROLE_CO_MAIN = "Co-Main"
ROLE_UNDERCARD = "Undercard"

def _fight_label(api: PrizefighterAPI, fight: dict) -> str:
    red = api.get_fighter(fight["red_corner_fighter_id"])
    blue = api.get_fighter(fight["blue_corner_fighter_id"])

    red_name = f'{red["first_name"]} {red["last_name"]}' if red else "?"
    blue_name = f'{blue["first_name"]} {blue["last_name"]}' if blue else "?"
    title = " [TITLE]" if fight["championship"] else ""
    return f'{fight["fight_id"]}: {red_name} vs {blue_name} ({fight["weight_limit"]} lbs){title}'


class CreateEventTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api

        self.date_fights = []      # every Scheduled fight loaded for the chosen date
        self.assignments = {}      # fight_id -> role string

        self._build_date_picker()
        self._build_assignment_area()
        self._build_card_details()

    # ---------- Construction ----------
    def _build_date_picker(self):
        box = ttk.LabelFrame(self, text="Card Date")
        box.pack(fill="x", padx=10, pady=10)

        ttk.Label(box, text="Date (dd-mm-yyyy):").pack(side="left", padx=5, pady=5)
        self.date_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.date_var, width=14).pack(side="left", padx=5, pady=5)

        ttk.Button(box, text="Load Scheduled Fights for This Date", command=self._on_load_date).pack(
            side="left", padx=10, pady=5)

        self.status_label = ttk.Label(box, text="", foreground="gray")
        self.status_label.pack(side="left", padx=15)

    def _build_assignment_area(self):
        area = ttk.Frame(self)
        area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- Available (unassigned) fights ---
        available_frame = ttk.LabelFrame(area, text="Available (Scheduled, not yet on this card)")
        available_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.available_list = tk.Listbox(available_frame, height=14, exportselection=False)
        self.available_list.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Middle: role-assignment buttons ---
        button_col = ttk.Frame(area)
        button_col.pack(side="left", fill="y", padx=5)

        ttk.Label(button_col, text="").pack(pady=20)  # vertical spacer
        ttk.Button(button_col, text="Set as Main Event  ->",
                  command=lambda: self._assign_role(ROLE_MAIN)).pack(fill="x", pady=4)
        ttk.Button(button_col, text="Add as Co-Main  ->",
                  command=lambda: self._assign_role(ROLE_CO_MAIN)).pack(fill="x", pady=4)
        ttk.Button(button_col, text="Add as Undercard  ->",
                  command=lambda: self._assign_role(ROLE_UNDERCARD)).pack(fill="x", pady=4)
        ttk.Button(button_col, text="<-  Remove From Card",
                  command=self._remove_from_card).pack(fill="x", pady=(20, 4))

        # --- Assigned fights, with their role ---
        assigned_frame = ttk.LabelFrame(area, text="On This Card")
        assigned_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        columns = ("role", "fight")
        self.assigned_tree = ttk.Treeview(assigned_frame, columns=columns, show="headings", height=14)
        self.assigned_tree.heading("role", text="Role")
        self.assigned_tree.heading("fight", text="Fight")
        self.assigned_tree.column("role", width=90, anchor="center")
        self.assigned_tree.column("fight", width=260, anchor="w")
        self.assigned_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_card_details(self):
        box = ttk.LabelFrame(self, text="Card Details")
        box.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Label(box, text="Headliner:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self.headliner_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.headliner_var, width=40).grid(
            row=0, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="Slogan (optional):").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        self.slogan_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.slogan_var, width=40).grid(
            row=1, column=1, sticky="w", padx=5, pady=4)

        ttk.Label(box, text="Arena:").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        self.arena_var = tk.StringVar()
        self.arena_combo = ttk.Combobox(box, textvariable=self.arena_var, state="readonly", width=37)
        self.arena_combo.grid(row=2, column=1, sticky="w", padx=5, pady=4)

        ttk.Button(box, text="Create Event", command=self._on_create_event).grid(
            row=3, column=0, sticky="w", padx=5, pady=(8, 5))

        self.refresh_reference_data()

    # ---------- Lifecycle ----------

    def on_tab_shown(self):
        self.refresh_reference_data()

    def refresh_reference_data(self):
        self._arena_options = [
            (a["arena_id"], f'{a["name"]} ({a["country"]})') for a in self.api.get_arenas()
        ]
        self.arena_combo["values"] = [label for _aid, label in self._arena_options]

    def _selected_arena_id(self):
        label = self.arena_var.get()
        for arena_id, option_label in self._arena_options:
            if option_label == label:
                return arena_id
        return None

    # ---------- Loading fights for a date ----------

    def _on_load_date(self):
        date_str = self.date_var.get().strip()
        self.date_fights = self.api.get_scheduled_fights_on_date(date_str)
        self.assignments = {}

        if not self.date_fights:
            self.status_label.config(text=f"No Scheduled fights found on {date_str}.")
        else:
            self.status_label.config(
                text=f"Loaded {len(self.date_fights)} scheduled fight(s) for {date_str}.")

        self._refresh_lists()

    # ---------- List rendering ----------

    def _refresh_lists(self):
        self.available_list.delete(0, tk.END)
        for fight in self.date_fights:
            if fight["fight_id"] not in self.assignments:
                self.available_list.insert(tk.END, _fight_label(self.api, fight))

        for item in self.assigned_tree.get_children():
            self.assigned_tree.delete(item)
        for fight in self.date_fights:
            role = self.assignments.get(fight["fight_id"])
            if role:
                self.assigned_tree.insert(
                    "", "end", iid=fight["fight_id"], values=(role, _fight_label(self.api, fight))
                )

    def _unassigned_fights(self):
        return [f for f in self.date_fights if f["fight_id"] not in self.assignments]

    # ---------- Role assignment ----------

    def _assign_role(self, role: str):
        selection = self.available_list.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Select an available fight first.")
            return

        fight = self._unassigned_fights()[selection[0]]

        if role == ROLE_MAIN and any(r == ROLE_MAIN for r in self.assignments.values()):
            messagebox.showerror(
                "Main Event Already Set",
                "This card already has a main event -- remove it first if you want to replace it.",
            )
            return

        self.assignments[fight["fight_id"]] = role
        self._refresh_lists()

    def _remove_from_card(self):
        selection = self.assigned_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select an assigned fight to remove.")
            return

        fight_id = selection[0]
        self.assignments.pop(fight_id, None)
        self._refresh_lists()

    # ---------- Save ----------

    def _on_create_event(self):
        date_str = self.date_var.get().strip()
        headliner = self.headliner_var.get().strip()
        arena_id = self._selected_arena_id()

        main_fight_ids = [fid for fid, role in self.assignments.items() if role == ROLE_MAIN]
        co_main_fight_ids = [fid for fid, role in self.assignments.items() if role == ROLE_CO_MAIN]
        undercard_fight_ids = [fid for fid, role in self.assignments.items() if role == ROLE_UNDERCARD]

        if not main_fight_ids:
            messagebox.showerror("Missing Main Event", "Assign a main event fight before saving.")
            return
        if arena_id is None:
            messagebox.showerror("Missing Arena", "Please select an arena.")
            return

        try:
            new_event = self.api.create_event(
                headliner=headliner,
                date=date_str,
                arena_id=arena_id,
                main_event_fight_id=main_fight_ids[0],
                co_main_fight_ids=co_main_fight_ids,
                undercard_fight_ids=undercard_fight_ids,
                slogan=self.slogan_var.get().strip(),
            )
        except EventError as e:
            messagebox.showerror("Could Not Create Event", str(e))
            return

        messagebox.showinfo("Event Created", f'Event #{new_event["event_id"]} ("{headliner}") created.')

        self.date_fights = []
        self.assignments = {}
        self.headliner_var.set("")
        self.slogan_var.set("")
        self.date_var.set("")
        self.status_label.config(text="")
        self._refresh_lists()
