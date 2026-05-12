# Test Inputs

## 2a) Flight Search — direct + connecting

**Direct flight (DFW → MEX):**
- Origin: `DFW`
- Destination: `MEX`
- Date: `2025-10-04`
- Expected: AA1000 leg 1, departs 09:54 arrives 11:26

**Connecting flight — valid (DFW → IAH → JFK, 81 min gap):**
- Origin: `DFW`
- Destination: `JFK`
- Date: `2025-10-04`
- Expected: UA2008 leg 1 (DFW→IAH, arr 15:04) + UA2010 leg 1 (IAH→JFK, dep 16:25)

**Connecting flight — known bug (DFW → LGA → JFK, 43 min gap, should NOT appear):**
- Origin: `DFW`
- Destination: `JFK`
- Date: `2025-10-04`
- DL3012 leg 2 (DFW→LGA, actual arr 14:29) + AA1061 leg 1 (LGA→JFK, actual dep 15:12) = 43 min gap — gap filter broken at milestone3_queries.py lines 95–101

---

## 2b) Flight Details

- Flight number: `AA1000`
- Date: `2025-10-04`
- Expected: 2 rows (leg 1 DFW→MEX 09:54–11:26, leg 2 MEX→DFW 12:11–16:44)

---

## 3a) Aircraft Utilization Report

- Airplane registration: `PLNEDAB43C9`
- Start date: `2025-10-04`
- End date: `2025-10-31`
- Expected: 120 flights

---

## 4b) Seat Availability

- Flight number: `AA1000`
- Leg number: `1`
- Date: `2025-10-04`
- Expected: Total 181, Booked 0, Remaining 181, Status: Available

---

## 4c) Book a Seat

**Simple booking:**
- Flight: `AA1000`, Leg: `1`, Date: `2025-10-04`, Seat: `1A`
- Customer name: `John Smith`, Phone: `2145550101`

**Multi-leg booking (WN4095: MDW → LGA → YYZ → IAD, overnight):**

| Step | Flight | Leg | Date       | Seat | Name     | Phone      |
|------|--------|-----|------------|------|----------|------------|
| 1    | WN4095 | 1   | 2025-10-04 | 1A   | Jane Doe | 2145550202 |
| 2    | WN4095 | 2   | 2025-10-04 | 1A   | Jane Doe | 2145550202 |
| 3    | WN4095 | 3   | 2025-10-04 | 1A   | Jane Doe | 2145550202 |

---

## 4d) Passenger Itinerary

After the multi-leg booking above:
- Search by name: `Jane Doe`
- Search by phone: `2145550202`
- Expected: 3 rows for WN4095 legs 1–3 (MDW→LGA→YYZ→IAD)
