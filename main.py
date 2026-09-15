import tkinter as tk

from tkinter import ttk

from api.PrizefighterAPI import PrizefighterAPI
from ui.settings import SettingsTab
from ui.add_fighter import AddFighterTab
from ui.edit_fighter import EditFighterTab


def main():
    root = tk.Tk()
    root.title("Prizefighters Promoter ML - Data Tracker")
    root.geometry("1000x650")

    api = PrizefighterAPI()

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    add_fighter_tab = AddFighterTab(notebook, api)
    edit_fighter_tab = EditFighterTab(notebook, api)
    settings_tab = SettingsTab(notebook, api)

    notebook.add(add_fighter_tab, text="Add Fighter")
    notebook.add(edit_fighter_tab, text="Edit Fighter")
    notebook.add(settings_tab, text="Settings")

    def on_tab_changed(event):
        current = notebook.nametowidget(notebook.select())
        if hasattr(current, "on_tab_shown"):
            current.on_tab_shown()

    notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

    root.mainloop()

if __name__ == "__main__":
    main()
