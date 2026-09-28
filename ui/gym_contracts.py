import tkinter as tk
from tkinter import ttk, messagebox

class GymContractsTab(ttk.Frame):
    """UI for managing gym contracts."""

    def __init__(self, parent, api):
        super().__init__(parent)
        self.api = api

        self.gym_lookup = {}
        self.fighter_lookup = {}

        # Variables
        self.gym_var = tk.StringVar()
        self.fighter_var = tk.StringVar()
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select a gym, fighter, and contract period.")

        self._build_ui()
        self._load_reference_data()

    def _build_ui(self):
        """ Build the Gym Contracts interface """
        container = ttk.Frame(self, padding=20)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)

        row = 0

        # ROW 1: STATUS
        status_frame = ttk.LabelFrame(container, text="Status", padding=10)
        status_frame.grid(row=row, column=0, columnspan=2, sticky="ew",)

        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, wraplength=500)
        self.status_label.pack(fill="x", anchor="w")
        row += 1

        # ROW 2: GYM SELECTION
        ttk.Label(container, text="Gym",).grid(row=row, column=0, sticky="w", pady=(0, 5))
        self.gym_combo = ttk.Combobox(container, textvariable=self.gym_var, state="readonly", width=30)
        self.gym_combo.grid(row=row, column=1, sticky="ew", pady=(0, 15))
        row += 1

        # ROW 3: FIGHTER SELECTION
        ttk.Label(container, text="Fighter",).grid(row=row, column=0, sticky="w", pady=(0, 5))
        self.fighter_combo = ttk.Combobox(container, textvariable=self.fighter_var, state="readonly")
        self.fighter_combo.grid(row=row, column=1, sticky="ew", pady=(0, 15))
        row += 1

        # ROW 4: CONTRACT DATES
        date_frame = ttk.Frame(container)
        date_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 20))

        # Start date
        ttk.Label(date_frame, text="Start Date (MM-DD-YYYY)").pack(side="left", padx=(10, 2))
        self.start_date_entry = ttk.Entry(
            date_frame,
            textvariable=self.start_date_var,
        )
        self.start_date_entry.pack(side="left", padx=(10, 2))

        # End date
        ttk.Label(date_frame, text="End Date (MM-DD-YYYY)",).pack(side="left", padx=(10, 2))
        self.end_date_entry = ttk.Entry(
            date_frame,
            textvariable=self.end_date_var,
        )
        self.end_date_entry.pack(side="left", padx=(10, 2))

        row += 1

        # ROW 5: SAVE BUTTON
        self.save_button = ttk.Button(container, text="Sign / Save Contract", command=self._save_contract)
        self.save_button.grid(row=row, column=0, sticky="ew", pady=(0, 15))

    # REFERENCE DATA
    def _load_reference_data(self):
        """ Load gyms and fighters into their respective comboboxes """
        self._load_gyms()
        self._load_fighters()

    def _load_gyms(self):
        """ Populate the gym combobox """
        gyms = self.api.get_gyms()

        self._gym_options = sorted(
            (
                (gym["id"], f'{gym["name"]}')
                for gym in gyms
            ),
            key=lambda option: option[1].lower()
        )
        self.gym_combo["values"] = [label for _gid, label in self._gym_options]
        self.gym_var.set("")

    def _load_fighters(self):
        """ Populate the fighter combobox """
        fighters = self.api.get_fighters()

        self._fighter_options = sorted(
            (
                (fighter["fighter_id"], f'{fighter["first_name"]} {fighter["last_name"]}')
                for fighter in fighters
            ),
            key=lambda option: option[1].lower()
        )
        self.fighter_combo["values"] = [label for _fid, label in self._fighter_options]
        self.fighter_var.set("")

    # SAVE CONTRACT
    def _save_contract(self):
        """ Validate input and save a new contract """
        gym_label = self.gym_var.get() # Fetch combobox selected
        fighter_label = self.fighter_var.get() # Fetch combobox selected

        if not gym_label:
            self._set_status("Please select a gym",  error=True)
            return
        if not fighter_label:
            self._set_status("Please select a fighter", error=True)
            return

        gym_id = next(gid for gid, label in self._gym_options if label == gym_label)
        fighter_id = next(fid for fid, label in self._fighter_options if label == fighter_label)

        # Retrieve dates
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            self._set_status("Please enter both the start and end dates.", error=True)
            return

        # Save through the API
        try:
            contract = self.api.save_contract(
                gym_id=gym_id,
                fighter_id=fighter_id,
                start_date=start_date,
                end_date=end_date,
            )

        except Exception as exc:
            self._set_status(str(exc), error=True)
            return

        # Success
        self._set_status(
            f'Contract {contract["contractID"]} successfully saved '
            f'for {fighter_label}.',
            error=False,
        )

        # Clear the dates for the next contract
        self.start_date_var.set("")
        self.end_date_var.set("")

    # STATUS
    def _set_status(self, message: str, error: bool = False):
        """Update the status label."""
        self.status_var.set(message)
        if error:
            self.status_label.configure(foreground="red")
        else:
            self.status_label.configure(foreground="green")