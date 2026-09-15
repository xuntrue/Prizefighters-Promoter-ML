import tkinter as tk

from tkinter import ttk
from datetime import date

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from api.PrizefighterAPI import PrizefighterAPI
from api.Fighter import format_full_name, format_birthdate_readable, compute_age

FLAG_MAX_SIZE = (90, 60)  # (max width, max height) in px; aspect ratio is preserved


class FighterPreviewFrame(ttk.Frame):
    def __init__(self, parent, api: PrizefighterAPI):
        super().__init__(parent)
        self.api = api
        self._latest_data = {}
        self._flag_photo = None  # keep a reference so Tk doesn't garbage-collect it

        self._build_widgets()
        self._rerender()

    # ---------- Construction ----------
    def _build_widgets(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=(10, 0))

        ttk.Label(header, text="Preview", font=("TkDefaultFont", 12, "bold")).pack(side="left")

        date_frame = ttk.LabelFrame(header, text="Today's Date")
        date_frame.pack(side="right")

        today = date.today()
        self.year_var = tk.IntVar(value=today.year)
        self.month_var = tk.IntVar(value=today.month)
        self.day_var = tk.IntVar(value=today.day)

        ttk.Spinbox(date_frame, from_=1900, to=2100, textvariable=self.year_var, width=5).pack(
            side="left", padx=2, pady=4
        )
        ttk.Spinbox(date_frame, from_=1, to=12, textvariable=self.month_var, width=3).pack(
            side="left", padx=2, pady=4
        )
        ttk.Spinbox(date_frame, from_=1, to=31, textvariable=self.day_var, width=3).pack(
            side="left", padx=2, pady=4
        )
        for var in (self.year_var, self.month_var, self.day_var):
            var.trace_add("write", lambda *_args: self._rerender())

        self.flag_label = ttk.Label(self)
        self.flag_label.pack(pady=(15, 0))

        self.full_name_label = ttk.Label(
            self, text="", font=("TkDefaultFont", 14, "bold"), wraplength=280, justify="center"
        )
        self.full_name_label.pack(pady=(8, 15))

        info_frame = ttk.Frame(self)
        info_frame.pack(fill="x", padx=15)

        self.hometown_label = ttk.Label(info_frame, text="")
        self.hometown_label.pack(anchor="w")

        self.birthdate_label = ttk.Label(info_frame, text="")
        self.birthdate_label.pack(anchor="w")

        self.age_label = ttk.Label(info_frame, text="")
        self.age_label.pack(anchor="w")

        self.division_label = ttk.Label(info_frame, text="", wraplength=280, justify="left")
        self.division_label.pack(anchor="w", pady=(12, 0))

        self.style_label = ttk.Label(info_frame, text="", wraplength=280, justify="left")
        self.style_label.pack(anchor="w", pady=(12, 0))

        self.record_label = ttk.Label(info_frame, text="")
        self.record_label.pack(anchor="w")

        if not PIL_AVAILABLE:
            ttk.Label(
                self, text="(Install Pillow to display flag images: pip install pillow)",
                foreground="gray",
            ).pack(pady=(15, 0))

    # ---------- External API ----------
    def render(self, data: dict):
        """  Update the preview with fresh data """
        self._latest_data = data
        self._rerender()

    # ---------- Internal rendering ----------
    def _rerender(self):
        data = self._latest_data
        self._render_full_name(data)
        self._render_flag(data)
        self._render_hometown(data)
        self._render_birthdate_and_age(data)
        self._render_stats(data)
        self._render_record(data)

    def _render_full_name(self, data):
        first = data.get("first_name")
        last = data.get("last_name")
        if not (first or "").strip() and not (last or "").strip():
            self.full_name_label.config(text="(Unnamed Fighter)")
            return
        name = format_full_name(first, last, data.get("nickname"), data.get("placement") or "None")
        self.full_name_label.config(text=name)

    def _render_flag(self, data):
        a2 = data.get("country_a2")
        path = self.api.get_flag_path(a2) if a2 else None

        if not path or not PIL_AVAILABLE:
            self.flag_label.config(image="", text="(no flag)" if a2 else "")
            self._flag_photo = None
            return

        try:
            image = Image.open(path)
            image.thumbnail(FLAG_MAX_SIZE)
            self._flag_photo = ImageTk.PhotoImage(image)
            self.flag_label.config(image=self._flag_photo, text="")
        except Exception:
            self.flag_label.config(image="", text="(flag unavailable)")
            self._flag_photo = None

    def _render_hometown(self, data):
        hometown = (data.get("hometown") or "").strip()
        country_name = data.get("country_name") or ""
        if hometown and country_name:
            self.hometown_label.config(text=f"{hometown}, {country_name}")
        else:
            self.hometown_label.config(text=hometown or country_name)

    def _render_birthdate_and_age(self, data):
        birthdate_str = data.get("birthdate") or ""
        readable = format_birthdate_readable(birthdate_str)

        if readable is None:
            self.birthdate_label.config(text="Born: —")
            self.age_label.config(text="Age: —")
            return

        self.birthdate_label.config(text=f"Born: {readable}")

        as_of = self._current_preview_date()
        age = compute_age(birthdate_str, as_of) if as_of else None
        if age is None:
            self.age_label.config(text="Age: —")
        else:
            years, months = age
            self.age_label.config(text=f"Age: {years} years, {months} months")

    def _render_stats(self, data):
        parts = []
        if data.get("weight_class_label"):
            parts.append(data["weight_class_label"])
        if data.get("reach") is not None:
            parts.append(f'{data["reach"]}" reach')
        self.division_label.config(text=" | ".join(parts))
        parts = []
        if data.get("stance_label"):
            parts.append(data["stance_label"])
        if data.get("style_label"):
            parts.append(data["style_label"])
        self.style_label.config(text=" | ".join(parts))

    def _render_record(self, data):
        wins, knockouts, losses, draws = (
            data.get("wins"),
            data.get("knockouts"),
            data.get("losses"),
            data.get("draws")
        )
        if None in (wins, knockouts, losses, draws):
            self.record_label.config(text="")
        else:
            self.record_label.config(text=f"Record: {wins}-{losses}-{draws} ({knockouts} KOs)")

    def _current_preview_date(self):
        try:
            return date(self.year_var.get(), self.month_var.get(), self.day_var.get())
        except (tk.TclError, ValueError):
            return None
