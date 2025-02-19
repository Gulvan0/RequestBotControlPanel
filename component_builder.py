import tkinter as tk
import tkinter.ttk as ttk
from tkinter.constants import END, LEFT, TOP


# TODO: Also add tooltip to the label
def build_option_row(parent: tk.Misc, option_name: str, initial_value: str, is_secret: bool = False) -> ttk.Entry:
    row = ttk.Frame(parent)
    name = ttk.Label(row, text=option_name, anchor='center', width=20)
    value = ttk.Entry(row, show="●" if is_secret else "")
    value.insert(END, initial_value)
    name.pack(side=LEFT, expand=False)
    value.pack(side=LEFT, expand=True, fill='x')
    row.pack(side=TOP, expand=False, fill='x', padx=2, pady=2)
    return value


def build_tabs(parent: ttk.Notebook, names: list[str]) -> list[ttk.Frame]:
    tabs = []
    for name in names:
        tab = ttk.Frame(parent)
        parent.add(tab, text=name, padding=(10, 10))
        tabs.append(tab)
    return tabs