import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "ecofit_db")

WARDS_COL = os.getenv("WARDS_COL", "wards_master")  # fallback to "wards"
SERVICE_COL = os.getenv("SERVICE_LOGS_COL", "service_logs")
COMPLAINTS_COL = os.getenv("COMPLAINTS_COL", "complaints")
WEATHER_COL = os.getenv("WEATHER_COL", "weather_hourly")

# 12 months (recommended)
SEED_START_DATE = os.getenv("SEED_START_DATE", "2025-03-01")  # 12 months back from 2026-03-ish
SEED_END_DATE = os.getenv("SEED_END_DATE", "")                # empty -> now

CLEAR_EXISTING = os.getenv("CLEAR_EXISTING", "0") == "1"
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "77"))

random.seed(RANDOM_SEED)

# Behavior knobs (tuned for balanced risk)
MISS_PROB = float(os.getenv("MISS_PROB", "0.03"))          # missed pickups ~3%
PARTIAL_PROB = float(os.getenv("PARTIAL_PROB", "0.06"))    # partial ~6%
BASE_COMPLAINT_RATE = float(os.getenv("BASE_COMPLAINT_RATE", "0.10"))  # per ward per hour

# Service schedule: more services on weekdays, fewer weekends
WEEKDAY_SERVICE_TRIPS = (2, 4)  # min/max per ward per day
WEEKEND_SERVICE_TRIPS = (1, 2)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

def hour_floor(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)

def day_floor(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def hour_range(start: datetime, end: datetime):
    cur = hour_floor(start)
    while cur < end:
        yield cur
        cur += timedelta(hours=1)

def day_range(start: datetime, end: datetime):
    cur = day_floor(start)
    while cur < end:
        yield cur
        cur += timedelta(days=1)

def load_wards(db) -> List[Dict[str, Any]]:
    wards = list(db[WARDS_COL].find({}, {"_id": 0, "wardId": 1, "wardName": 1, "wardNo": 1}))
    wards = [w for w in wards if w.get("wardId")]
    if wards:
        return wards
    wards = list(db["wards"].find({}, {"_id": 0, "wardId": 1, "wardName": 1, "wardNo": 1}))
    return [w for w in wards if w.get("wardId")]

def make_global_weather(ts: datetime) -> Dict[str, Any]:
    """
    Global Colombo-like weather.
    Creates rainy streaks + daily cycle -> gives model signal.
    """
    h = ts.hour
    # daily temp cycle
    temp = 28 + (3.0 if 11 <= h <= 15 else 0.6) + random.uniform(-1.0, 1.0)

    # rainy seasons effect (rough): Mar-May + Oct-Dec more rain
    m = ts.month
    seasonal = 0.10 if m in [3,4,5,10,11,12] else 0.06
    evening = 0.06 if 16 <= h <= 22 else 0.0
    storm = (random.random() < 0.015)

    p_rain = min(0.35, seasonal + evening + (0.12 if storm else 0.0))
    raining = random.random() < p_rain

    if raining:
        rainMm = round(random.uniform(0.5, 10.0) * (2.5 if storm else 1.0), 2)
        precipProb = round(random.uniform(0.55, 0.95), 2)
    else:
        rainMm = 0.0
        precipProb = round(random.uniform(0.0, 0.2), 2)

    wind = round(random.uniform(5.0, 18.0) + (8.0 if storm else 0.0), 2)

    return {
        "tsHour": ts,
        "tempC": round(temp, 2),
        "rainMm": rainMm,
        "windKph": wind,
        "precipMm": rainMm,
        "precipProb": precipProb,
        "source": "synthetic_seed_v2",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }

def outcome_for_hour(rainMm: float) -> str:
    # rain increases chance of missed/partial slightly
    miss = MISS_PROB * (1.6 if rainMm > 5 else 1.0)
    part = PARTIAL_PROB * (1.3 if rainMm > 5 else 1.0)
    r = random.random()
    if r < miss:
        return "MISSED"
    if r < miss + part:
        return "PARTIAL"
    return "COLLECTED"

def volume_level(rainMm: float, day_of_week: int) -> str:
    # weekend + rain -> higher
    base = random.random()
    bump = 0.10 if rainMm > 5 else 0.0
    bump += 0.06 if day_of_week >= 5 else 0.0
    x = base + bump
    if x < 0.33:
        return "LOW"
    if x < 0.78:
        return "MEDIUM"
    return "HIGH"

def service_trip_hours(day: datetime) -> List[int]:
    dow = day.weekday()
    if dow < 5:
        n = random.randint(*WEEKDAY_SERVICE_TRIPS)
    else:
        n = random.randint(*WEEKEND_SERVICE_TRIPS)
    # typical operating hours
    hours = sorted(random.sample(range(6, 20), k=n))
    return hours

def make_service_log(ts: datetime, ward: Dict[str, Any], rainMm: float) -> Dict[str, Any]:
    dow = ts.weekday()
    out = outcome_for_hour(rainMm)
    v = volume_level(rainMm, dow)
    # kg depends on volumeLevel
    kg = random.uniform(80, 500)
    if v == "HIGH":
        kg *= 1.7
    elif v == "MEDIUM":
        kg *= 1.2
    if rainMm > 5:
        kg *= 1.15  # wet waste heavier

    bins = int(random.uniform(3, 24) * (1.2 if v == "HIGH" else 1.0))

    return {
        "createdAt": ts,
        "updatedAt": ts,
        "wardId": ward["wardId"],
        "ward": {
            "wardId": ward["wardId"],
            "wardName": ward.get("wardName", ward["wardId"]),
            "wardNo": ward.get("wardNo"),
        },
        "outcome": out,
        "status": out,
        "volumeLevel": v,
        "estimatedKg": round(kg, 2),
        "binsCleared": bins,
        "notes": "synthetic_seed_v2",
    }

def complaint_rate(rainMm: float, missed_recent: int) -> float:
    # rain + missed pickups -> more complaints
    r = BASE_COMPLAINT_RATE
    if rainMm > 2:
        r *= 1.4
    if rainMm > 8:
        r *= 1.8
    if missed_recent > 0:
        r *= (1.0 + 0.8 * missed_recent)
    return min(0.85, r)

def make_complaint(ts: datetime, ward: Dict[str, Any], rainMm: float, missed_recent: int) -> Dict[str, Any]:
    # category distribution influenced by rain/missed
    if missed_recent > 0 and random.random() < 0.55:
        category = "MISSED_PICKUP"
    elif rainMm > 5 and random.random() < 0.45:
        category = "OVERFLOW"
    else:
        category = random.choices(
            ["BAD_ODOR", "ILLEGAL_DUMPING", "OVERFLOW", "MISSED_PICKUP"],
            weights=[0.30, 0.12, 0.28, 0.30],
            k=1
        )[0]

    severity = random.choices([1,2,3,4,5], weights=[0.12,0.20,0.34,0.22,0.12], k=1)[0]
    # rain pushes severity slightly
    if rainMm > 8 and severity < 5 and random.random() < 0.35:
        severity += 1

    return {
        "createdAt": ts,
        "updatedAt": ts,
        "wardId": ward["wardId"],
        "ward": {
            "wardId": ward["wardId"],
            "wardName": ward.get("wardName", ward["wardId"]),
            "wardNo": ward.get("wardNo"),
        },
        "category": category,
        "severity": severity,
        "status": "NEW",
        "description": f"Synthetic complaint: {category}",
        "source": "synthetic_seed_v2",
    }

def main():
    if not MONGO_URL:
        raise RuntimeError("❌ MONGO_URL missing in .env")

    start = parse_date(SEED_START_DATE)
    end = parse_date(SEED_END_DATE) if SEED_END_DATE else utc_now()

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    wards = load_wards(db)
    if not wards:
        raise RuntimeError("❌ No wards found in wards_master/wards")

    print(f"✅ wards: {len(wards)}")
    print(f"📅 range: {start.isoformat()} → {end.isoformat()}")

    if CLEAR_EXISTING:
        print("🧹 CLEAR_EXISTING=1: deleting previous synthetic_seed_v2 in range...")
        db[WEATHER_COL].delete_many({"tsHour": {"$gte": start, "$lt": end}, "source": "synthetic_seed_v2"})
        db[SERVICE_COL].delete_many({"createdAt": {"$gte": start, "$lt": end}, "notes": "synthetic_seed_v2"})
        db[COMPLAINTS_COL].delete_many({"createdAt": {"$gte": start, "$lt": end}, "source": "synthetic_seed_v2"})

    # indexes
    db[WEATHER_COL].create_index([("tsHour", ASCENDING)])
    db[SERVICE_COL].create_index([("createdAt", ASCENDING), ("wardId", ASCENDING)])
    db[COMPLAINTS_COL].create_index([("createdAt", ASCENDING), ("wardId", ASCENDING)])

    # ---- build weather hourly (global) ----
    weather_docs = []
    weather_by_hour: Dict[datetime, Dict[str, Any]] = {}

    for ts in hour_range(start, end):
        w = make_global_weather(ts)
        weather_docs.append(w)
        weather_by_hour[ts] = w

    if weather_docs:
        db[WEATHER_COL].insert_many(weather_docs)
    print(f"🌦 inserted weather_hourly: {len(weather_docs)}")

    # ---- build services & complaints ----
    service_docs = []
    complaint_docs = []

    # track missed count by ward over last 24h to drive complaints realistically
    missed_window: Dict[str, List[datetime]] = {w["wardId"]: [] for w in wards}

    for day in day_range(start, end):
        # service trips per ward today
        for ward in wards:
            wid = ward["wardId"]
            hours = service_trip_hours(day)

            for h in hours:
                ts = day + timedelta(hours=h, minutes=random.randint(0, 55))
                wh = hour_floor(ts)
                rainMm = float(weather_by_hour.get(wh, {}).get("rainMm", 0.0))
                sdoc = make_service_log(ts, ward, rainMm)
                service_docs.append(sdoc)

                if sdoc["outcome"] == "MISSED":
                    missed_window[wid].append(wh)

            # cleanup missed_window older than 24h
            cutoff = day - timedelta(hours=24)
            missed_window[wid] = [t for t in missed_window[wid] if t >= cutoff]

        # complaints hourly-like pattern for this day
        for h in range(7, 23):  # complaint activity 7AM-11PM
            ts = day + timedelta(hours=h, minutes=random.randint(0, 55))
            wh = hour_floor(ts)
            rainMm = float(weather_by_hour.get(wh, {}).get("rainMm", 0.0))

            for ward in wards:
                wid = ward["wardId"]
                missed_recent = len(missed_window[wid])
                rate = complaint_rate(rainMm, missed_recent)

                # Bernoulli per hour; some hours multiple complaints if rate high
                if random.random() < rate:
                    complaint_docs.append(make_complaint(ts, ward, rainMm, missed_recent))
                    if rate > 0.55 and random.random() < 0.35:
                        complaint_docs.append(make_complaint(ts, ward, rainMm, missed_recent))

    if service_docs:
        db[SERVICE_COL].insert_many(service_docs)
    if complaint_docs:
        db[COMPLAINTS_COL].insert_many(complaint_docs)

    print(f"🧾 inserted service_logs: {len(service_docs)}")
    print(f"📣 inserted complaints: {len(complaint_docs)}")
    print("✅ done.")

if __name__ == "__main__":
    main()