import os
import time
from typing import Any, Dict, Optional, Tuple

import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "ecofit_db")
WARDS_MASTER_COL = os.getenv("WARDS_MASTER_COL", "wards_master")

NOMINATIM_EMAIL = os.getenv("NOMINATIM_EMAIL", "your_email@example.com")
USER_AGENT = f"EcoFitMunicipal/1.0 ({NOMINATIM_EMAIL})"

# Colombo bounding box
COLOMBO_BOX = {
    "min_lat": 6.75,
    "max_lat": 7.10,
    "min_lng": 79.78,
    "max_lng": 79.95,
}

# Default fallback coordinate — wards sitting on this need updating
DEFAULT_LAT = 6.9271
DEFAULT_LNG = 79.8612


def get_db():
    if not MONGO_URL:
        raise RuntimeError("MONGO_URL missing in .env")
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def to_float(x: Any) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except Exception:
        return None


def in_colombo_box(lat: float, lng: float) -> bool:
    return (
        COLOMBO_BOX["min_lat"] <= lat <= COLOMBO_BOX["max_lat"]
        and COLOMBO_BOX["min_lng"] <= lng <= COLOMBO_BOX["max_lng"]
    )


def is_default_coord(lat: float, lng: float) -> bool:
    return round(lat, 4) == round(DEFAULT_LAT, 4) and round(lng, 4) == round(DEFAULT_LNG, 4)


def geocode_place(session: requests.Session, q: str) -> Optional[Tuple[float, float]]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    r = session.get(url, params=params, headers=headers, timeout=20)
    if r.status_code != 200:
        print(f"  Nominatim error {r.status_code}: {r.text[:200]}")
        r.raise_for_status()

    data = r.json()
    if not data:
        return None

    return float(data[0]["lat"]), float(data[0]["lon"])


def should_update(w: Dict[str, Any]) -> bool:
    c = w.get("center") or {}
    if not isinstance(c, dict):
        return True

    lat = to_float(c.get("lat"))
    lng = to_float(c.get("lng"))

    if lat is None or lng is None:
        return True

    # Update if sitting on the default Town Hall coordinate
    if is_default_coord(lat, lng):
        return True

    # Update if outside Colombo entirely
    if not in_colombo_box(lat, lng):
        return True

    return False


def main():
    db = get_db()
    col = db[WARDS_MASTER_COL]

    wards = list(col.find(
        {},
        projection={"_id": 1, "wardId": 1, "wardName": 1, "center": 1},
    ))

    if not wards:
        print("No wards found.")
        return

    print(f"Total wards: {len(wards)}")

    to_update = [w for w in wards if should_update(w)]
    print(f"Wards needing geocoding: {len(to_update)}")
    print()

    session = requests.Session()
    updated = 0
    skipped = 0
    failed = 0

    for w in wards:
        ward_id   = (w.get("wardId")   or "").strip()
        ward_name = (w.get("wardName") or "").strip()

        if not should_update(w):
            skipped += 1
            continue

        # Build query — try ward name first, fall back to ward ID
        query = (
            f"{ward_name}, Colombo, Sri Lanka"
            if ward_name
            else f"{ward_id.replace('_', ' ')}, Colombo, Sri Lanka"
        )

        try:
            # Respect Nominatim rate limit — 1 request per second
            time.sleep(1.1)

            result = geocode_place(session, query)

            if not result:
                # Try a broader query without the specific name
                time.sleep(1.1)
                broader = f"{ward_name} Colombo Sri Lanka"
                result = geocode_place(session, broader)

            if not result:
                print(f"NOT FOUND: {ward_id} | {ward_name} | query: {query}")
                failed += 1
                continue

            lat, lng = result

            # Sanity check — must be in Colombo
            if not in_colombo_box(lat, lng):
                print(f"OUT OF BOX: {ward_id} | {ward_name} -> {lat}, {lng} — skipping")
                failed += 1
                continue

            col.update_one(
                {"_id": w["_id"]},
                {"$set": {"center": {"lat": lat, "lng": lng}}},
            )

            updated += 1
            print(f"UPDATED: {ward_name:30s} -> {lat:.4f}, {lng:.4f}")

        except Exception as e:
            failed += 1
            print(f"ERROR: {ward_id} | {ward_name} -> {e}")

    print()
    print("✅ DONE")
    print(f"updated: {updated}  skipped: {skipped}  failed: {failed}")


if __name__ == "__main__":
    main()