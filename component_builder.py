import tkinter as tk
import tkinter.ttk as ttk
from tkinter import PhotoImage, Text
from tkinter.constants import CENTER, END, LEFT, TOP

from paths import get_image_path


class BasicText(Text):
    def __init__(self, parent: tk.Misc, initial_text: str):
        super().__init__(parent)
        self.insert(END, initial_text)

    def get_text(self) -> str:
        return self.get("1.0", END).strip()


class ReadOnlyText(BasicText):
    def __init__(self, parent: tk.Misc, initial_text: str):
        super().__init__(parent, initial_text)
        self.config(state='disabled')

    def set_text(self, text: str) -> None:
        self.config(state='normal')
        self.delete('1.0', END)
        self.insert(END, text)
        self.config(state='disabled')


class BasicEntry(ttk.Entry):
    def __init__(self, parent: tk.Misc, initial_text: str, is_secret: bool = False):
        super().__init__(parent, show="●" if is_secret else "")
        self.insert(END, initial_text)

    def get_text(self) -> str:
        return self.get().strip()


def build_button(parent: tk.Misc, image_name: str, command: ...) -> ttk.Button:
    image = build_image(image_name)
    btn = ttk.Button(parent, image=image, compound=LEFT, command=command)
    btn.img = image  # I @$%^ing hate having to write this hack
    return btn


def build_option_row(parent: tk.Misc, option_name: str, initial_value: str, is_secret: bool = False) -> BasicEntry:
    row = ttk.Frame(parent)
    name = ttk.Label(row, text=option_name, anchor='center', width=20)
    value = BasicEntry(row, initial_value, is_secret)
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


def build_image(name: str) -> PhotoImage:
    return PhotoImage(file=str(get_image_path(name)))


def build_horizontal_centered_frame(parent: tk.Misc) -> ttk.Frame:
    outer = ttk.Frame(parent)
    outer.pack(side=TOP, expand=True, fill='x')
    outer.columnconfigure(0, weight=1)
    outer.columnconfigure(1, weight=1)
    outer.columnconfigure(2, weight=1)
    inner = ttk.Frame(outer)
    inner.grid(row=0, column=1)
    return inner