import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "ecofit_db")

WARDS_COL = os.getenv("WARDS_COL", "wards_master")      # fallback handled
SERVICE_COL = os.getenv("SERVICE_LOGS_COL", "service_logs")
COMPLAINTS_COL = os.getenv("COMPLAINTS_COL", "complaints")
WEATHER_COL = os.getenv("WEATHER_COL", "weather_hourly")

# Seed time range
START_DATE_STR = os.getenv("SEED_START_DATE", "2026-02-01")  # Feb 1
END_DATE_STR = os.getenv("SEED_END_DATE", "")                # empty = now

# Volume
SERVICE_PER_WARD_PER_DAY_MIN = int(os.getenv("SERVICE_MIN_PER_DAY", "1"))
SERVICE_PER_WARD_PER_DAY_MAX = int(os.getenv("SERVICE_MAX_PER_DAY", "3"))

COMPLAINTS_PER_WARD_PER_DAY_MIN = int(os.getenv("COMPLAINTS_MIN_PER_DAY", "0"))
COMPLAINTS_PER_WARD_PER_DAY_MAX = int(os.getenv("COMPLAINTS_MAX_PER_DAY", "3"))

# Behavior tuning
MISS_PROB_BASE = float(os.getenv("MISS_PROB_BASE", "0.06"))   # base missed pickup probability
PARTIAL_PROB = float(os.getenv("PARTIAL_PROB", "0.08"))
RAINY_EXTRA_COMPLAINT_MULT = float(os.getenv("RAINY_EXTRA_COMPLAINT_MULT", "1.8"))

# If you want to clear data in this window before seeding:
CLEAR_EXISTING = os.getenv("CLEAR_EXISTING", "0") == "1"

# Deterministic seed
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
random.seed(RANDOM_SEED)


def parse_date(d: str) -> datetime:
    # date-only string -> UTC midnight
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hour_floor(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def day_range(start: datetime, end: datetime):
    cur = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while cur < end:
        yield cur
        cur += timedelta(days=1)


def hour_range(start: datetime, end: datetime):
    cur = hour_floor(start)
    while cur < end:
        yield cur
        cur += timedelta(hours=1)


def load_wards(db) -> List[Dict[str, Any]]:
    wards = list(db[WARDS_COL].find({}, {"_id": 0, "wardId": 1, "wardName": 1, "wardNo": 1}))
    if wards:
        wards = [w for w in wards if w.get("wardId")]
        return wards

    # fallback
    fallback = "wards"
    wards = list(db[fallback].find({}, {"_id": 0, "wardId": 1, "wardName": 1, "wardNo": 1}))
    wards = [w for w in wards if w.get("wardId")]
    return wards


def make_weather(ts: datetime) -> Dict[str, Any]:
    """
    Global weather for Colombo (same for all wards).
    Creates realistic daily temperature + occasional rain events.
    """
    hour = ts.hour

    # temp: 25–32 range with daily cycle
    base_temp = 28.0
    daily_variation = 3.0 * (1 if 11 <= hour <= 15 else 0.3)  # hotter midday
    tempC = base_temp + daily_variation + random.uniform(-0.8, 0.8)

    # rain events: higher in evenings + random storms
    rain_event_prob = 0.10 if 15 <= hour <= 22 else 0.05
    storm = random.random() < 0.03
    raining = (random.random() < rain_event_prob) or storm

    if raining:
        rainMm = round(random.uniform(1.0, 12.0) * (2.0 if storm else 1.0), 2)
        precipProb = round(random.uniform(0.6, 0.95), 2)
        precipMm = rainMm
    else:
        rainMm = 0.0
        precipProb = round(random.uniform(0.0, 0.2), 2)
        precipMm = 0.0

    windKph = round(random.uniform(4.0, 20.0) + (5.0 if storm else 0.0), 2)

    return {
        "tsHour": ts,
        "tempC": round(tempC, 2),
        "rainMm": rainMm,
        "windKph": windKph,
        "precipMm": precipMm,
        "precipProb": precipProb,
        "source": "synthetic_seed",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
    }


def make_service_log(ts: datetime, ward: Dict[str, Any], rainy: bool) -> Dict[str, Any]:
    """
    Creates one service log record.
    Fields are intentionally flexible to match your current docs.
    """
    # increase miss probability if rainy
    miss_prob = MISS_PROB_BASE * (1.4 if rainy else 1.0)
    r = random.random()

    if r < miss_prob:
        outcome = "MISSED"
    elif r < miss_prob + PARTIAL_PROB:
        outcome = "PARTIAL"
    else:
        outcome = "COLLECTED"

    volumeLevel = random.choices(
        ["LOW", "MEDIUM", "HIGH"],
        weights=[0.25, 0.5, 0.25],
        k=1
    )[0]

    return {
        "createdAt": ts,
        "updatedAt": ts,
        "wardId": ward["wardId"],  # helpful for aggregation
        "ward": {
            "wardId": ward["wardId"],
            "wardName": ward.get("wardName", ward["wardId"]),
            "wardNo": ward.get("wardNo"),
        },
        "outcome": outcome,
        "status": outcome,  # some of your code reads status/result/outcome
        "volumeLevel": volumeLevel,
        "estimatedKg": round(random.uniform(80, 900) * (1.2 if volumeLevel == "HIGH" else 1.0), 2),
        "binsCleared": int(random.uniform(2, 25)),
        "notes": "synthetic_seed",
    }


def make_complaint(ts: datetime, ward: Dict[str, Any], rainy: bool) -> Dict[str, Any]:
    category = random.choices(
        ["MISSED_PICKUP", "OVERFLOW", "BAD_ODOR", "ILLEGAL_DUMPING"],
        weights=[0.45, 0.25, 0.2, 0.1],
        k=1
    )[0]

    # rainy increases overflow/missed complaints a bit
    if rainy and random.random() < 0.35:
        category = random.choice(["OVERFLOW", "MISSED_PICKUP"])

    severity = random.choices([1, 2, 3, 4, 5], weights=[0.15, 0.25, 0.30, 0.20, 0.10], k=1)[0]

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
        "source": "synthetic_seed",
    }


def main():
    if not MONGO_URL:
        raise RuntimeError("MONGO_URL missing in .env")

    start = parse_date(START_DATE_STR)
    end = parse_date(END_DATE_STR) if END_DATE_STR else utc_now()

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    wards = load_wards(db)
    if not wards:
        raise RuntimeError(f"No wards found in '{WARDS_COL}' or fallback 'wards'. Add wards first.")

    print(f"✅ Wards loaded: {len(wards)}")
    print(f"📅 Seeding range: {start.isoformat()} → {end.isoformat()}")

    if CLEAR_EXISTING:
        print("🧹 CLEAR_EXISTING=1 → deleting existing seeded data in range...")
        db[WEATHER_COL].delete_many({"tsHour": {"$gte": start, "$lt": end}, "source": "synthetic_seed"})
        db[SERVICE_COL].delete_many({"createdAt": {"$gte": start, "$lt": end}, "notes": "synthetic_seed"})
        db[COMPLAINTS_COL].delete_many({"createdAt": {"$gte": start, "$lt": end}, "source": "synthetic_seed"})

    # Ensure indexes (safe)
    db[WEATHER_COL].create_index([("tsHour", ASCENDING)])
    db[SERVICE_COL].create_index([("createdAt", ASCENDING), ("wardId", ASCENDING)])
    db[COMPLAINTS_COL].create_index([("createdAt", ASCENDING), ("wardId", ASCENDING)])

    # ---- 1) Weather hourly (global) ----
    weather_docs = []
    weather_by_hour = {}

    for ts in hour_range(start, end):
        doc = make_weather(ts)
        weather_docs.append(doc)
        weather_by_hour[ts] = doc

    if weather_docs:
        db[WEATHER_COL].insert_many(weather_docs)
        print(f"🌦️ Inserted weather_hourly: {len(weather_docs)}")

    # ---- 2) Service logs + Complaints ----
    service_docs = []
    complaint_docs = []

    for day in day_range(start, end):
        # Determine if that day is rainy (if any hour has rainMm > 0)
        rainy_hours = [hour_floor(day + timedelta(hours=h)) for h in range(24)]
        day_rain_total = sum(weather_by_hour.get(h, {}).get("rainMm", 0.0) for h in rainy_hours)
        day_is_rainy = day_rain_total > 5.0  # threshold

        for ward in wards:
            # services per day for ward
            n_services = random.randint(SERVICE_PER_WARD_PER_DAY_MIN, SERVICE_PER_WARD_PER_DAY_MAX)
            service_hours = random.sample(range(6, 20), k=n_services)  # 6AM–8PM
            for h in service_hours:
                ts = day + timedelta(hours=h, minutes=random.randint(0, 50))
                rainy = weather_by_hour.get(hour_floor(ts), {}).get("rainMm", 0.0) > 0.0
                service_docs.append(make_service_log(ts, ward, rainy))

            # complaints per day for ward (higher if rainy)
            base_n = random.randint(COMPLAINTS_PER_WARD_PER_DAY_MIN, COMPLAINTS_PER_WARD_PER_DAY_MAX)
            if day_is_rainy:
                # add extra complaints sometimes
                if random.random() < 0.6:
                    base_n = int(round(base_n * RAINY_EXTRA_COMPLAINT_MULT + 1))

            n_complaints = max(0, base_n)
            if n_complaints > 0:
                complaint_hours = random.sample(range(7, 23), k=min(n_complaints, 16))
                for h in complaint_hours:
                    ts = day + timedelta(hours=h, minutes=random.randint(0, 55))
                    rainy = weather_by_hour.get(hour_floor(ts), {}).get("rainMm", 0.0) > 0.0
                    complaint_docs.append(make_complaint(ts, ward, rainy))

    if service_docs:
        db[SERVICE_COL].insert_many(service_docs)
        print(f"🧾 Inserted service_logs: {len(service_docs)}")
    if complaint_docs:
        db[COMPLAINTS_COL].insert_many(complaint_docs)
        print(f"📣 Inserted complaints: {len(complaint_docs)}")

    print("✅ Done seeding synthetic recent data.")


if __name__ == "__main__":
    main()