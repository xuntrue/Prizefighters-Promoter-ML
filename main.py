import tkinter as tk

from tkinter import ttk

from api.PrizefighterAPI import PrizefighterAPI
from ui.edit_weight_classes import EditWeightClassesTab

def main():
    root = tk.Tk()
    root.title("Prizefighters Promoter ML - Data Tracker")
    root.geometry("700x500")

    api = PrizefighterAPI()

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    weight_classes_tab = EditWeightClassesTab(notebook, api)
    notebook.add(weight_classes_tab, text="Settings")

    root.mainloop()

if __name__ == "__main__":
    main()
