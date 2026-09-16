import tkinter as tk

from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import FighterError
from ui.fighter_form import FighterFormFrame

class EditFighterTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api
        self.selected_fighter_id = None

        self._build_search()
        self._build_results_table()
        self._build_form()

    # ---------- Construction ----------
    def _build_search(self):
        search_frame = ttk.LabelFrame(self, text="Search Fighters")
        search_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(search_frame, text="First Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.search_first_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_first_var, width=20).grid(
            row=0, column=1, sticky="w", padx=5, pady=5
        )

        ttk.Label(search_frame, text="Last Name:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.search_last_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_last_var, width=20).grid(
            row=0, column=3, sticky="w", padx=5, pady=5
        )

        ttk.Button(search_frame, text="Search", command=self._on_search).grid(
            row=0, column=4, sticky="w", padx=10, pady=5
        )

    def _build_results_table(self):
        table_frame = ttk.LabelFrame(self, text="Results")
        table_frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        columns = ("fighter_id", "first_name", "last_name", "nickname", "country")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=6)
        self.tree.heading("fighter_id", text="ID")
        self.tree.heading("first_name", text="First Name")
        self.tree.heading("last_name", text="Last Name")
        self.tree.heading("nickname", text="Nickname")
        self.tree.heading("country", text="Nationality")

        self.tree.column("fighter_id", width=50, anchor="center")
        self.tree.column("first_name", width=120, anchor="w")
        self.tree.column("last_name", width=120, anchor="w")
        self.tree.column("nickname", width=120, anchor="w")
        self.tree.column("country", width=120, anchor="w")

        self.tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="left", fill="y", pady=5)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)

    def _build_form(self):
        form_container = ttk.LabelFrame(self, text="Edit Fighter")
        form_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.form = FighterFormFrame(form_container, self.api)
        self.form.pack(padx=10, pady=10, anchor="w")

        button_frame = ttk.Frame(form_container)
        button_frame.pack(padx=10, pady=(0, 10), anchor="w")

        self.update_button = ttk.Button(
            button_frame, text="Update Fighter", command=self._on_update, state="disabled"
        )
        self.update_button.pack(side="left", padx=5)

    # ---------- Behaviour ----------
    def on_tab_shown(self):
        self.form.refresh_reference_data()

    def _on_search(self):
        results = self.api.search_fighters(
            first_name=self.search_first_var.get(), last_name=self.search_last_var.get()
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        for fighter in results:
            self.tree.insert(
                "",
                "end",
                values=(fighter["fighter_id"], fighter["first_name"], fighter["last_name"], fighter["nickname"], 
                        self.api.countries.get_by_code(fighter["country"])["country_name"]
                )
            )

        if not results:
            messagebox.showinfo("No Results", "No fighters matched that search.")

    def _on_row_selected(self, event):
        selection = self.tree.selection()
        if not selection:
            return

        fighter_id = int(self.tree.item(selection[0], "values")[0])
        fighter = self.api.get_fighter(fighter_id)
        if fighter is None:
            return

        self.selected_fighter_id = fighter_id
        self.form.set_values(fighter)
        self.update_button.config(state="normal")

    def _on_update(self):
        if self.selected_fighter_id is None:
            return

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

        try:
            self.api.update_fighter(self.selected_fighter_id, **values)
        except FighterError as e:
            messagebox.showerror("Could Not Update Fighter", str(e))
            return

        messagebox.showinfo("Fighter Updated", "Changes saved.")
        self._on_search()  # refresh results table so any name change is reflected
