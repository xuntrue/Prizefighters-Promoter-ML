from tkinter import ttk, messagebox

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import FighterError
from api.Records import RecordError
from ui.fighter_form import FighterFormFrame

class AddFighterTab(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api

        ttk.Label(self, text="Add Fighter", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )

        self.form = FighterFormFrame(self, api)
        self.form.pack(padx=10, pady=10, anchor="w")

        button_frame = ttk.Frame(self)
        button_frame.pack(padx=10, pady=(0, 10), anchor="w")

        ttk.Button(button_frame, text="Save Fighter", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear", command=self.form.clear).pack(side="left", padx=5)

    def on_tab_shown(self):
        self.form.refresh_reference_data()

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

        try:
            new_fighter = self.api.add_fighter(**values)
        except (FighterError, RecordError) as e:
            messagebox.showerror("Could Not Save Fighter", str(e))
            return

        messagebox.showinfo(
            "Fighter Added",
            f"{new_fighter['first_name']} {new_fighter['last_name']} "
            f"was added with FighterID {new_fighter['fighter_id']}.",
        )
        self.form.clear()
