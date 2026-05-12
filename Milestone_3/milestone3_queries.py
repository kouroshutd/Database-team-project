"""Milestone 3 read-only query layer for GUI workflows."""

from __future__ import annotations

import re
from typing import Any

from mysql.connector import Error

from db import get_cursor


def _fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_cursor() as (_conn, cursor):
        cursor.execute(query, params)
        return cursor.fetchall() or []


def _fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with get_cursor() as (_conn, cursor):
        cursor.execute(query, params)
        return cursor.fetchone()


def search_trips(origin_code: str, destination_code: str, date: str) -> dict[str, list[dict[str, Any]]]:
    """Return direct and one-connection trips for a date."""
    direct = _fetch_all(
        """
        SELECT
            'Direct' AS Trip_type,
            f.Airline AS First_airline,
            li.Flight_number AS First_flight_number,
            li.Leg_no AS First_leg_no,
            li.Date AS First_date,
            NULL AS Second_date,
            fl.Dep_airport_code AS Origin_airport,
            NULL AS Connection_airport,
            li.Dep_time AS First_departure_time,
            li.Arr_time AS First_arrival_time,
            NULL AS Second_airline,
            NULL AS Second_flight_number,
            NULL AS Second_leg_no,
            NULL AS Second_departure_time,
            NULL AS Second_arrival_time,
            fl.Arr_airport_code AS Destination_airport
        FROM LEG_INSTANCE li
        JOIN FLIGHT_LEG fl
          ON fl.Flight_number = li.Flight_number
         AND fl.Leg_no = li.Leg_no
        JOIN FLIGHT f ON f.Number = li.Flight_number
        WHERE fl.Dep_airport_code = %s
          AND fl.Arr_airport_code = %s
          AND li.Date = %s
        ORDER BY li.Dep_time, li.Flight_number, li.Leg_no
        """,
        (origin_code, destination_code, date),
    )

    one_connection = _fetch_all(
        """
        SELECT
            'One-Connection' AS Trip_type,
            f1.Airline AS First_airline,
            li1.Flight_number AS First_flight_number,
            li1.Leg_no AS First_leg_no,
            li1.Date AS First_date,
            li2.Date AS Second_date,
            fl1.Dep_airport_code AS Origin_airport,
            fl1.Arr_airport_code AS Connection_airport,
            li1.Dep_time AS First_departure_time,
            li1.Arr_time AS First_arrival_time,
            f2.Airline AS Second_airline,
            li2.Flight_number AS Second_flight_number,
            li2.Leg_no AS Second_leg_no,
            li2.Dep_time AS Second_departure_time,
            li2.Arr_time AS Second_arrival_time,
            fl2.Arr_airport_code AS Destination_airport
        FROM LEG_INSTANCE li1
        JOIN FLIGHT_LEG fl1
          ON fl1.Flight_number = li1.Flight_number
         AND fl1.Leg_no = li1.Leg_no
        JOIN FLIGHT f1 ON f1.Number = li1.Flight_number
        JOIN LEG_INSTANCE li2
          ON li2.Date IN (li1.Date, DATE_ADD(li1.Date, INTERVAL 1 DAY))
        JOIN FLIGHT_LEG fl2
          ON fl2.Flight_number = li2.Flight_number
         AND fl2.Leg_no = li2.Leg_no
         AND fl2.Dep_airport_code = fl1.Arr_airport_code
        JOIN FLIGHT f2 ON f2.Number = li2.Flight_number
        WHERE fl1.Dep_airport_code = %s
          AND fl2.Arr_airport_code = %s
          AND li1.Date = %s
          AND fl1.Arr_airport_code <> fl1.Dep_airport_code
          AND fl1.Arr_airport_code <> fl2.Arr_airport_code
          AND TIMESTAMPDIFF(MINUTE,
                TIMESTAMP(li1.Date, li1.Arr_time),
                TIMESTAMP(li2.Date, li2.Dep_time)
              ) >= 60
        ORDER BY li1.Dep_time, li2.Dep_time
        LIMIT 100
        """,
        (origin_code, destination_code, date),
    )

    return {"direct": direct, "one_connection": one_connection}


def get_flight_details(flight_number: str, date: str) -> list[dict[str, Any]]:
    """Return flight details for every leg instance of one flight on one date."""
    return _fetch_all(
        """
        SELECT
            f.Airline,
            li.Flight_number,
            li.Leg_no,
            li.Date,
            li.Dep_time AS Departure_time,
            li.Arr_time AS Arrival_time
        FROM LEG_INSTANCE li
        JOIN FLIGHT f ON f.Number = li.Flight_number
        WHERE li.Flight_number = %s
          AND li.Date = %s
        ORDER BY li.Leg_no
        """,
        (flight_number, date),
    )


def get_seat_availability(flight_number: str, leg_no: int, date: str) -> dict[str, Any] | None:
    """Return seat availability summary for one leg instance."""
    row = _fetch_one(
        """
        SELECT
            li.Flight_number,
            li.Leg_no,
            li.Date,
            li.Airplane_id,
            COUNT(aps.Seat_no) AS Total_seats,
            COUNT(s.Seat_no) AS Booked_seats
        FROM LEG_INSTANCE li
        LEFT JOIN AIRPLANE_SEAT aps
          ON aps.Airplane_id = li.Airplane_id
        LEFT JOIN SEAT s
          ON s.Flight_number = li.Flight_number
         AND s.Leg_no = li.Leg_no
         AND s.Date = li.Date
         AND s.Seat_no = aps.Seat_no
        WHERE li.Flight_number = %s
          AND li.Leg_no = %s
          AND li.Date = %s
        GROUP BY li.Flight_number, li.Leg_no, li.Date, li.Airplane_id
        """,
        (flight_number, leg_no, date),
    )
    if row is None:
        return None

    total = int(row["Total_seats"])
    booked = int(row["Booked_seats"])
    remaining = total - booked
    return {
        "Flight_number": row["Flight_number"],
        "Leg_no": row["Leg_no"],
        "Date": row["Date"],
        "Airplane_id": row["Airplane_id"],
        "Total_seats": total,
        "Booked_seats": booked,
        "Remaining_seats": remaining,
        "Status": "Available" if remaining > 0 else "Not available",
    }


def get_passenger_itinerary(customer_lookup: str) -> list[dict[str, Any]]:
    """Return itinerary rows by customer name or phone."""
    lookup = customer_lookup.strip()
    if not lookup:
        return []

    normalized_phone = re.sub(r"\D+", "", lookup)
    if len(normalized_phone) == 10:
        return _fetch_all(
            """
            SELECT
                s.Customer_name,
                s.Cphone,
                s.Flight_number,
                s.Leg_no,
                s.Date,
                fl.Dep_airport_code,
                fl.Arr_airport_code,
                li.Dep_time,
                li.Arr_time,
                s.Seat_no
            FROM SEAT s
            JOIN FLIGHT_LEG fl
              ON fl.Flight_number = s.Flight_number
             AND fl.Leg_no = s.Leg_no
            JOIN LEG_INSTANCE li
              ON li.Flight_number = s.Flight_number
             AND li.Leg_no = s.Leg_no
             AND li.Date = s.Date
            WHERE s.Cphone = %s
            ORDER BY s.Date, s.Flight_number, s.Leg_no
            """,
            (normalized_phone,),
        )

    return _fetch_all(
        """
        SELECT
            s.Customer_name,
            s.Cphone,
            s.Flight_number,
            s.Leg_no,
            s.Date,
            fl.Dep_airport_code,
            fl.Arr_airport_code,
            li.Dep_time,
            li.Arr_time,
            s.Seat_no
        FROM SEAT s
        JOIN FLIGHT_LEG fl
          ON fl.Flight_number = s.Flight_number
         AND fl.Leg_no = s.Leg_no
        JOIN LEG_INSTANCE li
          ON li.Flight_number = s.Flight_number
         AND li.Leg_no = s.Leg_no
         AND li.Date = s.Date
        WHERE LOWER(s.Customer_name) = LOWER(%s)
        ORDER BY s.Date, li.Dep_time, s.Flight_number, s.Leg_no
        """,
        (lookup,),
    )


def get_aircraft_utilization(
    registration_number: str, start_date: str, end_date: str
) -> list[dict[str, Any]]:
    """Return aircraft utilization rows for one registration number and date range."""
    return _fetch_all(
        """
        SELECT
            CONCAT(a.Type_name, ' aircraft') AS Airplane,
            a.Type_name AS Airplane_type,
            a.Airplane_id AS Registration_number,
            COUNT(*) AS Number_of_flights
        FROM LEG_INSTANCE li
        JOIN AIRPLANE a ON a.Airplane_id = li.Airplane_id
        WHERE li.Airplane_id = %s
          AND li.Date BETWEEN %s AND %s
        GROUP BY a.Airplane_id, a.Type_name
        ORDER BY Number_of_flights DESC
        """,
        (registration_number, start_date, end_date),
    )


def safe_search_trips(origin_code: str, destination_code: str, date: str):
    try:
        if len(origin_code) != 3 or len(destination_code) != 3:
            return False, "Airport codes must be 3 letters."
        if origin_code == destination_code:
            return False, "Origin and destination cannot be the same."
        return True, search_trips(origin_code.upper(), destination_code.upper(), date)
    except Error as exc:
        return False, f"Error searching trips: {exc}"


def safe_get_flight_details(flight_number: str, date: str):
    try:
        return True, get_flight_details(flight_number.strip(), date)
    except Error as exc:
        return False, f"Error fetching flight details: {exc}"


def safe_get_seat_availability(flight_number: str, leg_no: int, date: str):
    try:
        result = get_seat_availability(flight_number.strip(), leg_no, date)
        if result is None:
            return False, "No matching leg instance found."
        return True, result
    except Error as exc:
        return False, f"Error fetching seat availability: {exc}"


def safe_get_passenger_itinerary(customer_lookup: str):
    try:
        if not customer_lookup.strip():
            return False, "Customer name or phone is required."
        return True, get_passenger_itinerary(customer_lookup)
    except Error as exc:
        return False, f"Error fetching itinerary: {exc}"


def search_bookable_legs_by_airports(origin: str, dest: str, date: str) -> list[dict[str, Any]]:
    return _fetch_all(
        """
        SELECT
            li.Flight_number,
            li.Leg_no,
            li.Date,
            fl.Dep_airport_code AS Dep_airport,
            fl.Arr_airport_code AS Arr_airport,
            li.Dep_time,
            li.Arr_time,
            li.No_of_avail_seats AS Avail_seats
        FROM LEG_INSTANCE li
        JOIN FLIGHT_LEG fl
          ON fl.Flight_number = li.Flight_number
         AND fl.Leg_no = li.Leg_no
        WHERE fl.Dep_airport_code = %s
          AND fl.Arr_airport_code = %s
          AND li.Date = %s
        ORDER BY li.Dep_time
        """,
        (origin, dest, date),
    )


def search_bookable_legs_by_flight(flight_number: str, date: str) -> list[dict[str, Any]]:
    return _fetch_all(
        """
        SELECT
            li.Flight_number,
            li.Leg_no,
            li.Date,
            fl.Dep_airport_code AS Dep_airport,
            fl.Arr_airport_code AS Arr_airport,
            li.Dep_time,
            li.Arr_time,
            li.No_of_avail_seats AS Avail_seats
        FROM LEG_INSTANCE li
        JOIN FLIGHT_LEG fl
          ON fl.Flight_number = li.Flight_number
         AND fl.Leg_no = li.Leg_no
        WHERE li.Flight_number = %s
          AND li.Date = %s
        ORDER BY li.Leg_no
        """,
        (flight_number, date),
    )


def safe_search_bookable_legs_by_airports(origin: str, dest: str, date: str):
    try:
        if len(origin) != 3 or len(dest) != 3:
            return False, "Airport codes must be 3 letters."
        if origin == dest:
            return False, "Origin and destination cannot be the same."
        return True, search_bookable_legs_by_airports(origin.upper(), dest.upper(), date)
    except Error as exc:
        return False, f"Error searching flights: {exc}"


def safe_search_bookable_legs_by_flight(flight_number: str, date: str):
    try:
        if not flight_number.strip():
            return False, "Flight number is required."
        return True, search_bookable_legs_by_flight(flight_number.strip(), date)
    except Error as exc:
        return False, f"Error searching flights: {exc}"


def safe_get_aircraft_utilization(registration_number: str, start_date: str, end_date: str):
    try:
        if not registration_number.strip():
            return False, "Registration number is required."
        return True, get_aircraft_utilization(registration_number.strip(), start_date, end_date)
    except Error as exc:
        return False, f"Error fetching aircraft utilization: {exc}"
