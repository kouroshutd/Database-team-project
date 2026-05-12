"""Tkinter GUI entry point for Milestone 3."""

from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
import re
from db import set_db_password, test_connection
from milestone3_queries import (
    safe_get_aircraft_utilization,
    safe_get_flight_details,
    safe_get_passenger_itinerary,
    safe_get_seat_availability,
    safe_search_trips,
    safe_search_bookable_legs_by_airports,
    safe_search_bookable_legs_by_flight,
)
from reservations import book_seat, cancel_reservation


def _valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _normalize_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")


class Milestone3GUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Airport Management System - Milestone 3")
        self.geometry("1100x760")
        self.minsize(980, 640)

        self.status_var = tk.StringVar(value="Ready")

        if not self._prompt_database_login():
            self.destroy()
            return

        self._build_layout()

    def _prompt_database_login(self) -> bool:
        """Prompt for MySQL password inside GUI and retry on failure."""
        dialog = tk.Toplevel(self)
        dialog.title("Database Login")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="Enter MySQL password").grid(row=0, column=0, padx=12, pady=(12, 6), sticky="w")
        password_entry = ttk.Entry(dialog, width=30, show="*")
        password_entry.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="we")
        password_entry.focus_set()

        result = {"ok": False, "cancelled": False}

        def try_login():
            password = password_entry.get()
            set_db_password(password)
            ok, message = test_connection()
            if ok:
                result["ok"] = True
                dialog.destroy()
                return
            messagebox.showerror("Database Connection Failed", message, parent=dialog)
            password_entry.delete(0, tk.END)
            password_entry.focus_set()

        def cancel():
            result["cancelled"] = True
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="e")
        ttk.Button(button_frame, text="Connect", command=try_login).pack(side="left", padx=(0, 8))
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side="left")

        dialog.bind("<Return>", lambda _event: try_login())
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dialog)
        return result["ok"] and not result["cancelled"]

    def _build_layout(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_trip = ttk.Frame(notebook)
        self.tab_flight = ttk.Frame(notebook)
        self.tab_seat = ttk.Frame(notebook)
        self.tab_book = ttk.Frame(notebook)
        self.tab_cancel = ttk.Frame(notebook)
        self.tab_itinerary = ttk.Frame(notebook)
        self.tab_utilization = ttk.Frame(notebook)

        notebook.add(self.tab_trip, text="Flight Search")
        notebook.add(self.tab_flight, text="Flight Details")
        notebook.add(self.tab_seat, text="Seat Availability")
        notebook.add(self.tab_book, text="Book Seat")
        notebook.add(self.tab_cancel, text="Cancel Reservation")
        notebook.add(self.tab_itinerary, text="Passenger Itinerary")
        notebook.add(self.tab_utilization, text="Aircraft Utilization")

        self._build_trip_tab()
        self._build_flight_details_tab()
        self._build_seat_availability_tab()
        self._build_book_tab()
        self._build_cancel_tab()
        self._build_itinerary_tab()
        self._build_utilization_tab()

        status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status_bar.pack(fill="x", padx=10, pady=(0, 10))

    def _set_status(self, text: str):
        self.status_var.set(text)

    @staticmethod
    def _clear_tree(tree: ttk.Treeview):
        for row_id in tree.get_children():
            tree.delete(row_id)

    @staticmethod
    def _render_rows(tree: ttk.Treeview, rows: list[dict]):
        for row in rows:
            values = [("" if row.get(col, "") is None else row.get(col, "")) for col in tree["columns"]]
            tree.insert("", "end", values=values)

    @staticmethod
    def _make_scrollable_tree(parent: ttk.Frame, columns: tuple[str, ...], height: int = 12, col_width: int = 130):
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True, pady=(12, 0))

        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=height)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=col_width, anchor="w")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        return tree

    def _build_trip_tab(self):
        frm = ttk.Frame(self.tab_trip, padding=12)
        frm.pack(fill="both", expand=True)

        controls = ttk.Frame(frm)
        controls.pack(fill="x")
        ttk.Label(controls, text="Origin code").grid(row=0, column=0, sticky="w")
        self.trip_origin = ttk.Entry(controls, width=14)
        self.trip_origin.grid(row=0, column=1, sticky="w", padx=(8, 16))

        ttk.Label(controls, text="Destination code").grid(row=0, column=2, sticky="w")
        self.trip_destination = ttk.Entry(controls, width=14)
        self.trip_destination.grid(row=0, column=3, sticky="w", padx=(8, 16))

        ttk.Label(controls, text="Date (YYYY-MM-DD)").grid(row=0, column=4, sticky="w")
        self.trip_date = ttk.Entry(controls, width=16)
        self.trip_date.grid(row=0, column=5, sticky="w", padx=(8, 16))

        ttk.Button(controls, text="Search", command=self.on_search_trips).grid(row=0, column=6, sticky="w")

        columns = (
            "Trip_type",
            "First_airline",
            "First_flight_number",
            "First_leg_no",
            "First_date",
            "Second_date",
            "Origin_airport",
            "Connection_airport",
            "First_departure_time",
            "First_arrival_time",
            "Second_airline",
            "Second_flight_number",
            "Second_leg_no",
            "Second_departure_time",
            "Second_arrival_time",
            "Destination_airport",
        )
        self.trip_tree = self._make_scrollable_tree(frm, columns, height=22, col_width=120)

    def _build_flight_details_tab(self):
        frm = ttk.Frame(self.tab_flight, padding=12)
        frm.pack(fill="both", expand=True)

        controls = ttk.Frame(frm)
        controls.pack(fill="x")

        ttk.Label(controls, text="Flight number").grid(row=0, column=0, sticky="w")
        self.details_flight = ttk.Entry(controls, width=16)
        self.details_flight.grid(row=0, column=1, sticky="w", padx=(8, 16))

        ttk.Label(controls, text="Date (YYYY-MM-DD)").grid(row=0, column=2, sticky="w")
        self.details_date = ttk.Entry(controls, width=16)
        self.details_date.grid(row=0, column=3, sticky="w", padx=(8, 16))

        ttk.Button(controls, text="Search", command=self.on_search_flight_details).grid(row=0, column=4, sticky="w")

        columns = ("Airline", "Flight_number", "Leg_no", "Date", "Departure_time", "Arrival_time")
        self.details_tree = self._make_scrollable_tree(frm, columns, height=22, col_width=170)

    def _build_seat_availability_tab(self):
        frm = ttk.Frame(self.tab_seat, padding=12)
        frm.pack(fill="both", expand=True)

        controls = ttk.Frame(frm)
        controls.pack(fill="x")

        ttk.Label(controls, text="Flight number").grid(row=0, column=0, sticky="w")
        self.seat_flight = ttk.Entry(controls, width=14)
        self.seat_flight.grid(row=0, column=1, sticky="w", padx=(8, 16))

        ttk.Label(controls, text="Leg number").grid(row=0, column=2, sticky="w")
        self.seat_leg = ttk.Entry(controls, width=10)
        self.seat_leg.grid(row=0, column=3, sticky="w", padx=(8, 16))

        ttk.Label(controls, text="Date (YYYY-MM-DD)").grid(row=0, column=4, sticky="w")
        self.seat_date = ttk.Entry(controls, width=16)
        self.seat_date.grid(row=0, column=5, sticky="w", padx=(8, 16))

        ttk.Button(controls, text="Check", command=self.on_check_seats).grid(row=0, column=6, sticky="w")

        columns = (
            "Flight_number",
            "Leg_no",
            "Date",
            "Airplane_id",
            "Total_seats",
            "Booked_seats",
            "Remaining_seats",
            "Status",
        )
        self.seat_tree = self._make_scrollable_tree(frm, columns, height=10, col_width=130)

    def _build_book_tab(self):
        frm = ttk.Frame(self.tab_book, padding=12)
        frm.pack(fill="both", expand=True)

        # --- Search section ---
        search_frame = ttk.LabelFrame(frm, text="Find a Flight", padding=8)
        search_frame.pack(fill="x")

        ttk.Label(search_frame, text="Origin").grid(row=0, column=0, sticky="w")
        self.book_origin = ttk.Entry(search_frame, width=8)
        self.book_origin.grid(row=0, column=1, sticky="w", padx=(4, 12))

        ttk.Label(search_frame, text="Destination").grid(row=0, column=2, sticky="w")
        self.book_dest = ttk.Entry(search_frame, width=8)
        self.book_dest.grid(row=0, column=3, sticky="w", padx=(4, 12))

        ttk.Label(search_frame, text="Date (YYYY-MM-DD)").grid(row=0, column=4, sticky="w")
        self.book_search_date = ttk.Entry(search_frame, width=14)
        self.book_search_date.grid(row=0, column=5, sticky="w", padx=(4, 12))

        ttk.Button(search_frame, text="Search by airports", command=self.on_book_search_airports).grid(row=0, column=6, sticky="w")

        ttk.Label(search_frame, text="Flight number").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.book_search_flight = ttk.Entry(search_frame, width=14)
        self.book_search_flight.grid(row=1, column=1, sticky="w", padx=(4, 12), pady=(8, 0))

        ttk.Label(search_frame, text="Date (YYYY-MM-DD)").grid(row=1, column=4, sticky="w", pady=(8, 0))
        self.book_search_flight_date = ttk.Entry(search_frame, width=14)
        self.book_search_flight_date.grid(row=1, column=5, sticky="w", padx=(4, 12), pady=(8, 0))

        ttk.Button(search_frame, text="Search by flight", command=self.on_book_search_flight).grid(row=1, column=6, sticky="w", pady=(8, 0))

        # --- Results treeview ---
        result_cols = ("Flight_number", "Leg_no", "Date", "Dep_airport", "Arr_airport", "Dep_time", "Arr_time", "Avail_seats")
        self.book_search_tree = self._make_scrollable_tree(frm, result_cols, height=8, col_width=110)
        self.book_search_tree.bind("<<TreeviewSelect>>", self._on_book_row_select)

        # --- Booking section ---
        book_frame = ttk.LabelFrame(frm, text="Book Selected Leg", padding=8)
        book_frame.pack(fill="x", pady=(8, 0))

        self.book_selected_label = ttk.Label(book_frame, text="No flight selected", foreground="gray")
        self.book_selected_label.grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 8))

        ttk.Label(book_frame, text="Seat").grid(row=1, column=0, sticky="w")
        self.book_seat_no = ttk.Entry(book_frame, width=10)
        self.book_seat_no.grid(row=1, column=1, sticky="w", padx=(4, 12))

        ttk.Label(book_frame, text="Customer name").grid(row=1, column=2, sticky="w")
        self.book_name = ttk.Entry(book_frame, width=22)
        self.book_name.grid(row=1, column=3, sticky="w", padx=(4, 12))

        ttk.Label(book_frame, text="Phone").grid(row=1, column=4, sticky="w")
        self.book_phone = ttk.Entry(book_frame, width=14)
        self.book_phone.grid(row=1, column=5, sticky="w", padx=(4, 12))

        ttk.Button(book_frame, text="Book seat", command=self.on_book_seat).grid(row=1, column=6, sticky="w")

        self.book_message = tk.StringVar(value="")
        self.book_message_label = tk.Label(book_frame, textvariable=self.book_message, fg="#1f7a1f")
        self.book_message_label.grid(row=2, column=0, columnspan=7, sticky="w", pady=(8, 0))

        self._book_selected: dict = {}

    def _build_itinerary_tab(self):
        frm = ttk.Frame(self.tab_itinerary, padding=12)
        frm.pack(fill="both", expand=True)

        controls = ttk.Frame(frm)
        controls.pack(fill="x")
        ttk.Label(controls, text="Customer name").grid(row=0, column=0, sticky="w")
        self.itinerary_name = ttk.Entry(controls, width=24)
        self.itinerary_name.grid(row=0, column=1, sticky="w", padx=(8, 16))
        ttk.Button(controls, text="Search by name", command=self.on_search_itinerary_by_name).grid(
            row=0, column=2, sticky="w", padx=(0, 20)
        )

        ttk.Label(controls, text="Phone").grid(row=0, column=3, sticky="w")
        self.itinerary_phone = ttk.Entry(controls, width=18)
        self.itinerary_phone.grid(row=0, column=4, sticky="w", padx=(8, 16))
        ttk.Button(controls, text="Search by phone", command=self.on_search_itinerary_by_phone).grid(
            row=0, column=5, sticky="w"
        )

        columns = (
            "Customer_name",
            "Cphone",
            "Flight_number",
            "Leg_no",
            "Date",
            "Dep_airport_code",
            "Arr_airport_code",
            "Dep_time",
            "Arr_time",
            "Seat_no",
        )
        self.itinerary_tree = self._make_scrollable_tree(frm, columns, height=22, col_width=130)

    def _build_cancel_tab(self):
        frm = ttk.Frame(self.tab_cancel, padding=12)
        frm.pack(fill="both", expand=True)

        controls = ttk.Frame(frm)
        controls.pack(fill="x")

        ttk.Label(controls, text="Flight number").grid(row=0, column=0, sticky="w")
        self.cancel_flight = ttk.Entry(controls, width=14)
        self.cancel_flight.grid(row=0, column=1, sticky="w", padx=(8, 12))

        ttk.Label(controls, text="Leg number").grid(row=0, column=2, sticky="w")
        self.cancel_leg = ttk.Entry(controls, width=10)
        self.cancel_leg.grid(row=0, column=3, sticky="w", padx=(8, 12))

        ttk.Label(controls, text="Date (YYYY-MM-DD)").grid(row=0, column=4, sticky="w")
        self.cancel_date = ttk.Entry(controls, width=16)
        self.cancel_date.grid(row=0, column=5, sticky="w", padx=(8, 12))

        ttk.Label(controls, text="Seat number").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.cancel_seat = ttk.Entry(controls, width=12)
        self.cancel_seat.grid(row=1, column=1, sticky="w", padx=(8, 12), pady=(10, 0))

        ttk.Button(controls, text="Cancel reservation", command=self.on_cancel_reservation).grid(
            row=1, column=2, sticky="w", pady=(10, 0)
        )

        self.cancel_message = tk.StringVar(value="")
        self.cancel_message_label = tk.Label(frm, textvariable=self.cancel_message, fg="#1f7a1f")
        self.cancel_message_label.pack(anchor="w", pady=(14, 0))

        columns = ("Flight_number", "Leg_no", "Date", "Seat_no", "Result", "Message")
        self.cancel_result_tree = self._make_scrollable_tree(frm, columns, height=10, col_width=180)

    def _build_utilization_tab(self):
        frm = ttk.Frame(self.tab_utilization, padding=12)
        frm.pack(fill="both", expand=True)

        controls = ttk.Frame(frm)
        controls.pack(fill="x")

        ttk.Label(controls, text="Airplane registration").grid(row=0, column=0, sticky="w")
        self.util_registration = ttk.Entry(controls, width=20)
        self.util_registration.grid(row=0, column=1, sticky="w", padx=(8, 12))

        ttk.Label(controls, text="Start date").grid(row=0, column=2, sticky="w")
        self.util_start = ttk.Entry(controls, width=16)
        self.util_start.grid(row=0, column=3, sticky="w", padx=(8, 12))

        ttk.Label(controls, text="End date").grid(row=0, column=4, sticky="w")
        self.util_end = ttk.Entry(controls, width=16)
        self.util_end.grid(row=0, column=5, sticky="w", padx=(8, 12))

        ttk.Button(controls, text="Run report", command=self.on_aircraft_utilization).grid(row=0, column=6, sticky="w")

        columns = ("Airplane", "Airplane_type", "Registration_number", "Number_of_flights")
        self.util_tree = self._make_scrollable_tree(frm, columns, height=22, col_width=200)

    def on_search_trips(self):
        origin = self.trip_origin.get().strip().upper()
        destination = self.trip_destination.get().strip().upper()
        date = self.trip_date.get().strip()
        if not _valid_date(date):
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD.")
            return

        ok, result = safe_search_trips(origin, destination, date)
        self._clear_tree(self.trip_tree)
        if not ok:
            messagebox.showerror("Search Error", result)
            self._set_status("Trip search failed")
            return

        all_rows = result["direct"] + result["one_connection"]
        if not all_rows:
            messagebox.showinfo("No Results", "No matching records found.")
            self._set_status("No rows found.")
            return
        self._render_rows(self.trip_tree, all_rows)
        self._set_status(f"Trip search completed: {len(all_rows)} rows")

    def on_search_flight_details(self):
        flight_number = self.details_flight.get().strip()
        date = self.details_date.get().strip()
        if not _valid_date(date):
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD.")
            return

        ok, result = safe_get_flight_details(flight_number, date)
        self._clear_tree(self.details_tree)
        if not ok:
            messagebox.showerror("Search Error", result)
            self._set_status("Flight details failed")
            return

        if not result:
            messagebox.showinfo("No Results", "No matching records found.")
            self._set_status("No rows found.")
            return
        self._render_rows(self.details_tree, result)
        self._set_status(f"Flight details loaded: {len(result)} rows")

    def on_check_seats(self):
        flight_number = self.seat_flight.get().strip()
        leg_raw = self.seat_leg.get().strip()
        date = self.seat_date.get().strip()

        if not leg_raw.isdigit():
            messagebox.showerror("Invalid Leg", "Leg number must be a whole number.")
            return
        if not _valid_date(date):
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD.")
            return

        ok, result = safe_get_seat_availability(flight_number, int(leg_raw), date)
        self._clear_tree(self.seat_tree)
        if not ok:
            messagebox.showerror("Seat Availability Error", result)
            self._set_status("Seat check failed")
            return

        self._render_rows(self.seat_tree, [result])
        self._set_status("Seat availability loaded")

    def on_book_search_airports(self):
        origin = self.book_origin.get().strip().upper()
        dest = self.book_dest.get().strip().upper()
        date = self.book_search_date.get().strip()
        if not _valid_date(date):
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD.")
            return
        ok, result = safe_search_bookable_legs_by_airports(origin, dest, date)
        self._clear_tree(self.book_search_tree)
        self._book_selected = {}
        self.book_selected_label.configure(text="No flight selected", foreground="gray")
        if not ok:
            messagebox.showerror("Search Error", result)
            return
        if not result:
            messagebox.showinfo("No Results", "No matching flights found.")
            return
        self._render_rows(self.book_search_tree, result)
        self._set_status(f"Found {len(result)} flight legs")

    def on_book_search_flight(self):
        flight_number = self.book_search_flight.get().strip()
        date = self.book_search_flight_date.get().strip()
        if not _valid_date(date):
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD.")
            return
        ok, result = safe_search_bookable_legs_by_flight(flight_number, date)
        self._clear_tree(self.book_search_tree)
        self._book_selected = {}
        self.book_selected_label.configure(text="No flight selected", foreground="gray")
        if not ok:
            messagebox.showerror("Search Error", result)
            return
        if not result:
            messagebox.showinfo("No Results", "No matching flights found.")
            return
        self._render_rows(self.book_search_tree, result)
        self._set_status(f"Found {len(result)} flight legs")

    def _on_book_row_select(self, _event):
        sel = self.book_search_tree.selection()
        if not sel:
            return
        values = self.book_search_tree.item(sel[0], "values")
        cols = self.book_search_tree["columns"]
        row = dict(zip(cols, values))
        self._book_selected = {
            "flight_number": row["Flight_number"],
            "leg_no": row["Leg_no"],
            "date": row["Date"],
        }
        self.book_selected_label.configure(
            text=f"Flight {row['Flight_number']}  Leg {row['Leg_no']}  {row['Date']}  "
                 f"{row['Dep_airport']} → {row['Arr_airport']}  "
                 f"{row['Dep_time']} – {row['Arr_time']}  "
                 f"({row['Avail_seats']} seats available)",
            foreground="black",
        )
        self.book_message.set("")

    def on_book_seat(self):
        if not self._book_selected:
            messagebox.showerror("No Flight Selected", "Search for a flight and select a row first.")
            return

        flight_number = self._book_selected["flight_number"]
        leg_no = int(self._book_selected["leg_no"])
        date = self._book_selected["date"]
        seat_no = self.book_seat_no.get().strip()
        customer_name = self.book_name.get().strip()
        phone = re.sub(r'\D', '', self.book_phone.get().strip())

        ok, message = book_seat(flight_number, leg_no, date, seat_no, customer_name, phone)
        self.book_message.set(message)
        if not ok:
            self.book_message_label.configure(fg="#d35400")
            self._set_status("Booking failed")
            return

        self.book_message_label.configure(fg="#1f7a1f")
        self._set_status("Booking saved")
        self.book_seat_no.delete(0, tk.END)
        self.book_name.delete(0, tk.END)
        self.book_phone.delete(0, tk.END)
        self._book_selected = {}
        self.book_selected_label.configure(text="No flight selected", foreground="gray")
        self._clear_tree(self.book_search_tree)

    def _run_itinerary_search(self, lookup: str):
        ok, result = safe_get_passenger_itinerary(lookup)
        self._clear_tree(self.itinerary_tree)
        if not ok:
            messagebox.showerror("Itinerary Error", result)
            self._set_status("Itinerary lookup failed")
            return

        if not result:
            messagebox.showinfo("No Results", "No matching records found.")
            self._set_status("No rows found.")
            return
        self._render_rows(self.itinerary_tree, result)
        self._set_status(f"Itinerary rows: {len(result)}")

    def on_search_itinerary_by_name(self):
        lookup = self.itinerary_name.get().strip()
        if not lookup:
            messagebox.showerror("Input Error", "Customer name is required.")
            return
        self._run_itinerary_search(lookup)

    def on_search_itinerary_by_phone(self):
        lookup = re.sub(r'\D', '', self.itinerary_phone.get().strip())
        if not lookup:
            messagebox.showerror("Input Error", "Phone is required.")
            return
        self._run_itinerary_search(lookup)

    def on_aircraft_utilization(self):
        reg = self.util_registration.get().strip()
        start_date = self.util_start.get().strip()
        end_date = self.util_end.get().strip()
        if not _valid_date(start_date) or not _valid_date(end_date):
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD for start and end.")
            return
        start_date = _normalize_date(start_date)
        end_date = _normalize_date(end_date)
        if end_date < start_date:
            messagebox.showerror("Invalid Range", "End date must be on or after start date.")
            return

        ok, result = safe_get_aircraft_utilization(reg, start_date, end_date)
        self._clear_tree(self.util_tree)
        if not ok:
            messagebox.showerror("Utilization Error", result)
            self._set_status("Utilization report failed")
            return

        if not result:
            messagebox.showinfo("No Results", "No matching records found.")
            self._set_status("No rows found.")
            return
        self._render_rows(self.util_tree, result)
        self._set_status(f"Utilization rows: {len(result)}")

    def on_cancel_reservation(self):
        flight_number = self.cancel_flight.get().strip()
        leg_raw = self.cancel_leg.get().strip()
        date = self.cancel_date.get().strip()
        seat_no = self.cancel_seat.get().strip()

        if not leg_raw.isdigit():
            self.cancel_message.set("Leg number must be a whole number.")
            self.cancel_message_label.configure(fg="#d35400")
            return
        if not _valid_date(date):
            self.cancel_message.set("Date must use YYYY-MM-DD.")
            self.cancel_message_label.configure(fg="#d35400")
            return

        ok, message = cancel_reservation(flight_number, int(leg_raw), date, seat_no)
        self.cancel_message.set(message)
        if ok:
            self.cancel_result_tree.insert(
                "",
                0,
                values=(flight_number, leg_raw, date, seat_no, "Success", message),
            )
            self.cancel_message_label.configure(fg="#1f7a1f")
            self._set_status("Reservation canceled")
            self.cancel_flight.delete(0, tk.END)
            self.cancel_leg.delete(0, tk.END)
            self.cancel_date.delete(0, tk.END)
            self.cancel_seat.delete(0, tk.END)
        else:
            self.cancel_message_label.configure(fg="#d35400")
            self._set_status("Cancellation failed")


def main():
    root = Milestone3GUI()
    if not root.winfo_exists():
        return
    root.mainloop()


def _run_tests():
    import sys
    password = sys.argv[2] if len(sys.argv) > 2 else input("DB password: ")
    from db import set_db_password
    set_db_password(password)

    print("\n--- Trip search DFW -> JFK on 2025-10-04 ---")
    ok, result = safe_search_trips("DFW", "JFK", "2025-10-04")
    if not ok:
        print("ERROR:", result)
    else:
        print(f"Direct: {len(result['direct'])} rows")
        for r in result["direct"]:
            print(f"  {r['First_flight_number']} {r['Origin_airport']}->{r['Destination_airport']} dep={r['First_departure_time']} arr={r['First_arrival_time']}")
        print(f"Connections: {len(result['one_connection'])} rows")
        for r in result["one_connection"]:
            print(f"  {r['First_flight_number']} via {r['Connection_airport']} -> {r['Second_flight_number']}  dep={r['First_departure_time']} arr1={r['First_arrival_time']} dep2={r['Second_departure_time']}")

    print("\n--- Trip search DFW -> MEX on 2025-10-04 ---")
    ok, result = safe_search_trips("DFW", "MEX", "2025-10-04")
    if not ok:
        print("ERROR:", result)
    else:
        print(f"Direct: {len(result['direct'])} rows")
        for r in result["direct"]:
            print(f"  {r['First_flight_number']} dep={r['First_departure_time']} arr={r['First_arrival_time']}")
        print(f"Connections: {len(result['one_connection'])} rows")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        _run_tests()
    else:
        main()
