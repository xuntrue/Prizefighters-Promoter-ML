import tkinter as tk

from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Weight_Classes import WeightClassError, MIN_WEIGHT, MAX_WEIGHT

class EditWeightClassesTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)

        self.api = api

        self.selected_weight_limit = None  # tracks which row is being edited, if any

        self._build_form()
        self._build_table()

        self._refresh_table()

    def _build_form(self):
        form = ttk.LabelFrame(self, text="Add / Edit Weight Class")
        form.pack(fill="x", padx=10, pady=10)

        ttk.Label(form, text=f"Weight Limit (lbs, {MIN_WEIGHT}-{MAX_WEIGHT}):").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self.weight_limit_var = tk.StringVar()
        self.weight_limit_entry = ttk.Entry(form, textvariable=self.weight_limit_var, width=10)
        self.weight_limit_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(form, text="Weight Class Name:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.weight_class_var = tk.StringVar()
        self.weight_class_entry = ttk.Entry(form, textvariable=self.weight_class_var, width=25)
        self.weight_class_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        button_frame = ttk.Frame(form)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        self.save_button = ttk.Button(button_frame, text="Add Weight Class", command=self._on_save)
        self.save_button.pack(side="left", padx=5)

        self.clear_button = ttk.Button(button_frame, text="Clear", command=self._clear_form)
        self.clear_button.pack(side="left", padx=5)

    def _build_table(self):
        table_frame = ttk.LabelFrame(self, text="Existing Weight Classes")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        columns = ("weight_limit", "weight_class")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        self.tree.heading("weight_limit", text="Weight Limit (lbs)")
        self.tree.heading("weight_class", text="Weight Class")
        self.tree.column("weight_limit", width=140, anchor="center")
        self.tree.column("weight_class", width=200, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="left", fill="y", pady=5)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        action_frame = ttk.Frame(table_frame)
        action_frame.pack(side="left", fill="y", padx=10, pady=5)

        ttk.Button(action_frame, text="Delete Selected", command=self._on_delete).pack(
            pady=5, fill="x"
        )

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.api.get_weight_classes():
            self.tree.insert("", "end", values=(row["weight_limit"], row["weight_class"]))

    def _on_row_selected(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        self.selected_weight_limit = int(values[0])
        self.weight_limit_var.set(values[0])
        self.weight_class_var.set(values[1])
        self.save_button.config(text="Update Weight Class")

    def _clear_form(self):
        self.selected_weight_limit = None
        self.weight_limit_var.set("")
        self.weight_class_var.set("")
        self.save_button.config(text="Add Weight Class")
        self.tree.selection_remove(self.tree.selection())

    def _on_save(self):
        weight_limit_raw = self.weight_limit_var.get().strip()
        weight_class = self.weight_class_var.get().strip()

        if not weight_limit_raw.isdigit():
            messagebox.showerror("Invalid Input", "Weight limit must be a whole number.")
            return

        weight_limit = int(weight_limit_raw)

        try:
            if self.selected_weight_limit is None:
                self.api.add_weight_class(weight_limit, weight_class)
            else:
                self.api.update_weight_class(self.selected_weight_limit, weight_limit, weight_class)
        except WeightClassError as e:
            messagebox.showerror("Invalid Weight Class", str(e))
            return

        self._refresh_table()
        self._clear_form()

    def _on_delete(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select a weight class to delete.")
            return

        values = self.tree.item(selection[0], "values")
        weight_limit = int(values[0])
        weight_class = values[1]

        confirm = messagebox.askyesno("Confirm Delete", f'Delete "{weight_class}" ({weight_limit} lbs)?')
        if not confirm:
            return

        try:
            self.api.delete_weight_class(weight_limit)
        except WeightClassError as e:
            messagebox.showerror("Error", str(e))
            return

        self._refresh_table()
        self._clear_form()
