import tkinter as tk

from tkinter import ttk

from api.PrizefighterAPI import PrizefighterAPI
from ui.settings import SettingsTab
from ui.add_fighter import AddFighterTab
from ui.edit_fighter import EditFighterTab
from ui.rankings import RankingsTab
from ui.schedule_fight import ScheduleFightTab
from ui.create_event import CreateEventTab
from ui.record_fight_prefight import RecordFightPrefightTab
from ui.record_fight_result import RecordFightResultTab

def main():
    root = tk.Tk()
    root.title("Prizefighters Promoter ML - Data Tracker")
    root.geometry("1150x800")

    api = PrizefighterAPI()

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    add_fighter_tab = AddFighterTab(notebook, api)
    edit_fighter_tab = EditFighterTab(notebook, api)
    rankings_tab = RankingsTab(notebook, api)
    schedule_fight_tab = ScheduleFightTab(notebook, api)
    create_event_tab = CreateEventTab(notebook, api)
    record_prefight_tab = RecordFightPrefightTab(notebook, api)
    record_result_tab = RecordFightResultTab(notebook, api)
    settings_tab = SettingsTab(notebook, api)

    notebook.add(add_fighter_tab, text="Add Fighter")
    notebook.add(edit_fighter_tab, text="Edit Fighter")
    notebook.add(rankings_tab, text="Rankings")
    notebook.add(schedule_fight_tab, text="Schedule Fight")
    notebook.add(create_event_tab, text="Create Event")
    notebook.add(record_prefight_tab, text="Pre-Fight Meta")
    notebook.add(record_result_tab, text="Record Result")
    notebook.add(settings_tab, text="Settings")

    def on_tab_changed(event):
        current = notebook.nametowidget(notebook.select())
        if hasattr(current, "on_tab_shown"):
            current.on_tab_shown()

    notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

    root.mainloop()


if __name__ == "__main__":
    main()
